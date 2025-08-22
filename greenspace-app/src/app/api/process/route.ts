import { NextRequest, NextResponse } from 'next/server';
import { ProcessingConfig, ProcessingStatus } from '@/types';
import { v4 as uuidv4 } from 'uuid';
import { promises as fs } from 'fs';
import path from 'path';
import { spawn } from 'child_process';
import { setProcessingJob, updateProcessingJob, getProcessingJob } from '@/lib/processing-store';

export async function POST(request: NextRequest) {
  try {
    const config: ProcessingConfig = await request.json();
    
    if (!config.city && !(config.cities && config.cities.length)) {
      return NextResponse.json(
        { error: 'City or cities are required' },
        { status: 400 }
      );
    }

    // Generate unique processing ID
    const processingId = uuidv4();
    
    // Create initial status
    const status: ProcessingStatus = {
      id: processingId,
      status: 'pending',
      progress: 0,
      message: 'Initializing processing...',
      startTime: new Date(),
    };
    
    setProcessingJob(processingId, status);
    console.log(`Created processing job ${processingId} for ${config.city?.city || (config.cities ? config.cities.length + ' cities' : 'unknown')}`);

    // Start processing asynchronously
    processInBackground(processingId, config);

    return NextResponse.json({ processingId });
  } catch (error) {
    console.error('Error starting processing:', error);
    return NextResponse.json(
      { error: 'Failed to start processing' },
      { status: 500 }
    );
  }
}

async function processInBackground(processingId: string, config: ProcessingConfig) {
  try {
    console.log(`Starting optimized background processing for ${processingId}`);
    
    // Create output directory
    const outputDir = path.join(process.cwd(), 'public', 'outputs', processingId);
    await fs.mkdir(outputDir, { recursive: true });
    console.log(`Created output directory: ${outputDir}`);

    // Update status
    updateProcessingJob(processingId, {
      status: 'downloading',
      progress: 5,
      message: 'Initializing satellite processing...'
    });

    // Annual comparison mode: run two annual analyses (baseline and compare)
    if (config.annualMode && config.cities && config.cities.length) {
      // Multi-city batch annual comparison (sequential to limit load)
      const baselineYear = config.baselineYear ?? 2020;
      const compareYear = config.compareYear ?? baselineYear;
      const batchSummaries: any[] = [];

      async function runMonthForCity(city: any, year: number, month: number, label: string) {
        const mm = month.toString().padStart(2, '0');
        const monthDir = path.join(outputDir, city.city.replace(/\s+/g, '_'), label, mm);
        await fs.mkdir(monthDir, { recursive: true });
        const configPathMonth = path.join(monthDir, 'config.json');
        await fs.writeFile(configPathMonth, JSON.stringify({
          city,
          startMonth: mm,
          startYear: year,
          endMonth: mm,
          endYear: year,
          ndviThreshold: config.ndviThreshold,
          cloudCoverageThreshold: config.cloudCoverageThreshold,
          enableVegetationIndices: config.enableVegetationIndices,
          enableAdvancedCloudDetection: config.enableAdvancedCloudDetection,
          outputDir: monthDir
        }, null, 2));
        await runPythonScript('satellite_processor_fixed.py', configPathMonth, processingId);
        const res = await collectResults(monthDir);
        const s: any = res.summary || {};
        // Emit incremental preview appended to shared previews list
        const job = getProcessingJob(processingId);
        const existingPreviews = (job?.result as any)?.previews || [];
        const thumb = (res.outputFiles || []).find((f: string) => f.endsWith('vegetation_highlighted.png')) || (res.outputFiles || [])[0] || '';
        const newPreview = thumb ? { label: `${city.city} ${label} ${year}-${mm}`, image: thumb, month, year, type: label==='baseline'?'baseline':'compare', veg: res.vegetationPercentage || 0, cloud: s.cloud_excluded_percentage || 0, highPct: s.high_density_percentage || 0, medPct: s.medium_density_percentage || 0, lowPct: s.low_density_percentage || 0, cityName: city.city } : null;
        if (newPreview) {
          updateProcessingJob(processingId, {
            status: 'processing',
            message: `${city.city} ${label} ${year}-${mm} completed`,
            result: {
              ...(job?.result as any),
              previews: [...existingPreviews, newPreview]
            } as any
          });
          try {
            const statusPath = path.join(outputDir, 'status.json');
            await fs.writeFile(statusPath, JSON.stringify(getProcessingJob(processingId), null, 2));
          } catch {}
        }
        return {
          veg: res.vegetationPercentage || 0,
          ndviMean: s.ndvi_mean || 0,
          highPct: s.high_density_percentage || 0,
          medPct: s.medium_density_percentage || 0,
          lowPct: s.low_density_percentage || 0,
          cloud: s.cloud_excluded_percentage || 0
        };
      }

      for (const city of config.cities) {
        const baseMonthly: any[] = [];
        const compMonthly: any[] = [];
        for (let m = 1; m <= 12; m++) {
          try {
            baseMonthly.push(await runMonthForCity(city, baselineYear, m, 'baseline'));
          } catch {}
        }
        for (let m = 1; m <= 12; m++) {
          try {
            compMonthly.push(await runMonthForCity(city, compareYear, m, 'compare'));
          } catch {}
        }
        const avg = (arr: number[]) => arr.length ? arr.reduce((a,b)=>a+b,0)/arr.length : 0;
        const baselineVegetation = avg(baseMonthly.map(x=>x.veg));
        const compareVegetation = avg(compMonthly.map(x=>x.veg));
        const percentChange = baselineVegetation!==0 ? ((compareVegetation-baselineVegetation)/baselineVegetation)*100 : 0;
        const highPct = avg(compMonthly.map(x=>x.highPct));
        const medPct = avg(compMonthly.map(x=>x.medPct));
        const lowPct = avg(compMonthly.map(x=>x.lowPct));
        const cloudExcludedPct = avg(compMonthly.map(x=>x.cloud));
        batchSummaries.push({
          city,
          baselineYear,
          compareYear,
          baselineVegetation,
          compareVegetation,
          percentChange,
          monthlyNdviMeanBaseline: baseMonthly.map(x=>x.ndviMean),
          monthlyNdviMeanCompare: compMonthly.map(x=>x.ndviMean),
          monthlyVegBaseline: baseMonthly.map(x=>x.veg),
          monthlyVegCompare: compMonthly.map(x=>x.veg),
          highPct,
          medPct,
          lowPct,
          cloudExcludedPct,
          vegetationPct: compareVegetation
        });
        // Persist intermediate batch status
        updateProcessingJob(processingId, {
          status: 'processing',
          progress: Math.min(95, Math.round((batchSummaries.length / config.cities.length) * 95)),
          message: `Completed ${batchSummaries.length}/${config.cities.length} cities`,
          result: {
            downloadedImages: 0,
            processedComposites: 0,
            vegetationPercentage: 0,
            highDensityPercentage: 0,
            mediumDensityPercentage: 0,
            lowDensityPercentage: 0,
            outputFiles: [],
            summary: undefined,
            annualComparison: undefined,
            batchSummaries
          } as any
        });
        try {
          const statusPath = path.join(outputDir, 'status.json');
          await fs.writeFile(statusPath, JSON.stringify(getProcessingJob(processingId), null, 2));
        } catch {}
      }

      updateProcessingJob(processingId, {
        status: 'completed',
        progress: 100,
        message: 'Batch annual comparison completed!',
        endTime: new Date(),
        result: {
          downloadedImages: 0,
          processedComposites: 0,
          vegetationPercentage: 0,
          highDensityPercentage: 0,
          mediumDensityPercentage: 0,
          lowDensityPercentage: 0,
          outputFiles: [],
          summary: undefined,
          annualComparison: undefined,
          batchSummaries
        } as any
      });
      return;
    }

    if (config.annualMode) {
      const baselineYear = config.baselineYear ?? 2020;
      const compareYear = config.compareYear ?? baselineYear;
      const totalMonths = 24; // 12 baseline + 12 compare
      let completedMonths = 0;

      // Helper to run one month using single best scene selection (fixed script)
      async function runMonth(year: number, month: number, label: string) {
        const mm = month.toString().padStart(2, '0');
        const monthDir = path.join(outputDir, label, mm);
        await fs.mkdir(monthDir, { recursive: true });
        const configPathMonth = path.join(monthDir, 'config.json');
        await fs.writeFile(configPathMonth, JSON.stringify({
          city: config.city,
          startMonth: mm,
          startYear: year,
          endMonth: mm,
          endYear: year,
          ndviThreshold: config.ndviThreshold,
          cloudCoverageThreshold: config.cloudCoverageThreshold,
          enableVegetationIndices: config.enableVegetationIndices,
          enableAdvancedCloudDetection: config.enableAdvancedCloudDetection,
          outputDir: monthDir
        }, null, 2));
        console.log(`Running monthly processor for ${label} ${year}-${mm} (best scene per month)...`);
        await runPythonScript('satellite_processor_fixed.py', configPathMonth, processingId);
        const res = await collectResults(monthDir);
        // Build a preview object if an image exists
        const previewImage = (res.outputFiles || []).find((f: string) => f.endsWith('vegetation_highlighted.png'))
          || (res.outputFiles || []).find((f: string) => f.endsWith('ndvi_visualization.png'))
          || '';
        const s = res.summary || {} as any;
        return { res, preview: previewImage ? { label: `${label} ${year}-${mm}`, image: previewImage, month, year, type: label === 'baseline' ? 'baseline' : 'compare', veg: res.vegetationPercentage || 0, cloud: s.cloud_excluded_percentage || 0, highPct: s.high_density_percentage || 0, medPct: s.medium_density_percentage || 0, lowPct: s.low_density_percentage || 0 } : null };
      }

      async function runYearMonthly(year: number, label: string) {
        const monthly: { month: number; veg: number }[] = [];
        const previews: { label: string; image: string }[] = [];
        for (let m = 1; m <= 12; m++) {
          try {
            const { res, preview } = await runMonth(year, m, label);
            if (res && typeof res.vegetationPercentage === 'number') {
              monthly.push({ month: m, veg: res.vegetationPercentage });
            }
            if (preview) previews.push(preview);

            // Incremental UI update with previews and coarse progress
            completedMonths += 1;
            const job = getProcessingJob(processingId);
            const existingPreviews = (job?.result as any)?.previews || [];
            const newPreviews = preview ? [...existingPreviews, preview] : existingPreviews;
            const percent = Math.min(95, Math.round((completedMonths / totalMonths) * 95));
            const partial = {
              status: 'processing',
              progress: percent,
              message: `${label} ${year}-${m.toString().padStart(2, '0')} completed`,
              result: {
                downloadedImages: completedMonths,
                processedComposites: completedMonths,
                vegetationPercentage: res?.vegetationPercentage || 0,
                highDensityPercentage: 0,
                mediumDensityPercentage: 0,
                lowDensityPercentage: 0,
                ndviThreshold: config.ndviThreshold,
                outputFiles: [],
                summary: undefined,
                previews: newPreviews
              } as any
            } as any;

            updateProcessingJob(processingId, partial);
            // Persist to disk for durability across restarts
            try {
              const statusPath = path.join(outputDir, 'status.json');
              await fs.writeFile(statusPath, JSON.stringify(getProcessingJob(processingId), null, 2));
            } catch (e) {
              console.warn('Failed to persist file-backed status:', e);
            }
          } catch (e) {
            console.warn(`Month ${m} ${year} failed:`, e);
          }
        }
        const count = monthly.length || 1;
        const avgVeg = monthly.reduce((s, r) => s + r.veg, 0) / count;
        return { averageVegetation: avgVeg, monthlyCount: monthly.length, previews };
      }

      const baselineAgg = await runYearMonthly(baselineYear, 'baseline');
      const compareAgg = await runYearMonthly(compareYear, 'compare');

      const annualComparison = {
        baselineYear,
        baselineVegetation: baselineAgg.averageVegetation,
        compareYear,
        compareVegetation: compareAgg.averageVegetation,
        percentChange: baselineAgg.averageVegetation !== 0
          ? ((compareAgg.averageVegetation - baselineAgg.averageVegetation) / baselineAgg.averageVegetation) * 100
          : 0
      };

      updateProcessingJob(processingId, {
        status: 'completed',
        progress: 100,
        message: 'Annual comparison (monthly best) completed successfully!',
        endTime: new Date(),
        result: {
          downloadedImages: compareAgg.monthlyCount,
          processedComposites: compareAgg.monthlyCount,
          vegetationPercentage: compareAgg.averageVegetation,
          highDensityPercentage: 0,
          mediumDensityPercentage: 0,
          lowDensityPercentage: 0,
          outputFiles: [],
          summary: undefined,
          annualComparison,
          previews: [...baselineAgg.previews, ...compareAgg.previews]
        }
      });

      console.log(`Annual monthly-best comparison completed for ${processingId}`);
    } else {
      // Save configuration for Python script (single-range mode)
      const configPath = path.join(outputDir, 'config.json');
      await fs.writeFile(configPath, JSON.stringify({
        city: config.city,
        startMonth: config.startMonth,
        startYear: config.startYear,
        endMonth: config.endMonth,
        endYear: config.endYear,
        ndviThreshold: config.ndviThreshold,
        cloudCoverageThreshold: config.cloudCoverageThreshold,
        enableVegetationIndices: config.enableVegetationIndices,
        enableAdvancedCloudDetection: config.enableAdvancedCloudDetection,
        outputDir: outputDir
      }, null, 2));
      console.log(`Saved config to: ${configPath}`);

      console.log('Running optimized satellite processor...');
      await runPythonScript('satellite_processor_fixed.py', configPath, processingId);

      console.log('Collecting results...');
      const results = await collectResults(outputDir);
      console.log('Results collected:', results);
      
      updateProcessingJob(processingId, {
        status: 'completed',
        progress: 100,
        message: 'Processing completed successfully!',
        endTime: new Date(),
        result: results
      });

      console.log(`Optimized processing completed successfully for ${processingId}`);
    }

  } catch (error) {
    console.error('Processing error:', error);
    updateProcessingJob(processingId, {
      status: 'failed',
      progress: 0,
      message: `Processing failed: ${error instanceof Error ? error.message : 'Unknown error'}`,
      endTime: new Date()
    });
  }
}



function runPythonScript(scriptName: string, configPath: string, processingId: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(process.cwd(), 'python_scripts', scriptName);
    const pythonPath = path.join(process.cwd(), 'venv', 'bin', 'python');
    
    console.log(`Running Python script: ${pythonPath} ${scriptPath} ${configPath}`);
    console.log(`Script exists: ${require('fs').existsSync(scriptPath)}`);
    console.log(`Python exists: ${require('fs').existsSync(pythonPath)}`);
    console.log(`Current working directory: ${process.cwd()}`);
    
    // Check if files exist before running
    if (!require('fs').existsSync(scriptPath)) {
      reject(new Error(`Python script not found: ${scriptPath}`));
      return;
    }
    
    if (!require('fs').existsSync(pythonPath)) {
      reject(new Error(`Python interpreter not found: ${pythonPath}. Please ensure virtual environment is set up.`));
      return;
    }
    
    // Use virtual environment's Python interpreter
    const pythonProcess = spawn(pythonPath, [scriptPath, configPath], {
      cwd: process.cwd(),
      env: {
        ...process.env,
        PATH: `${path.join(process.cwd(), 'venv', 'bin')}:${process.env.PATH}`,
        PYTHONPATH: path.join(process.cwd(), 'python_scripts')
      }
    });

    let stdout = '';
    let stderr = '';

    pythonProcess.stdout.on('data', (data) => {
      const output = data.toString();
      stdout += output;
      console.log(`[${scriptName}] ${output.trim()}`);
      
      // Parse progress updates from Python script output
      const lines = output.split('\n');
      for (const line of lines) {
        if (line.includes('PROGRESS:')) {
          const match = line.match(/PROGRESS:(\d+)/);
          if (match) {
            const baseProgress = getBaseProgressForScript(scriptName);
            const scriptProgress = parseInt(match[1]);
            const totalProgress = baseProgress + (scriptProgress * getProgressRangeForScript(scriptName) / 100);
            
            updateProcessingJob(processingId, {
              progress: Math.round(totalProgress)
            });
          }
        }
      }
    });

    pythonProcess.stderr.on('data', (data) => {
      const error = data.toString();
      stderr += error;
      console.error(`[${scriptName}] ERROR: ${error.trim()}`);
    });

    pythonProcess.on('close', (code) => {
      console.log(`[${scriptName}] Process closed with code ${code}`);
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`Python script ${scriptName} failed with code ${code}: ${stderr}`));
      }
    });

    pythonProcess.on('error', (error) => {
      console.error(`[${scriptName}] Process error:`, error);
      reject(error);
    });
  });
}

function getBaseProgressForScript(scriptName: string): number {
  switch (scriptName) {
    case 'download_satellite_images.py': return 10;
    case 'preprocess_satellite_images.py': return 40;
    case 'vegetation_highlighter.py': return 70;
    default: return 0;
  }
}

function getProgressRangeForScript(scriptName: string): number {
  switch (scriptName) {
    case 'download_satellite_images.py': return 30; // 10-40%
    case 'preprocess_satellite_images.py': return 30; // 40-70%
    case 'vegetation_highlighter.py': return 30; // 70-100%
    default: return 10;
  }
}

async function collectResults(outputDir: string) {
  try {
    console.log(`Collecting results from: ${outputDir}`);
    
    // Look for vegetation analysis directory
    const vegAnalysisDir = path.join(outputDir, 'vegetation_analysis');
    
    let vegetationPercentage = 0;
    let highDensityPercentage = 0;
    let mediumDensityPercentage = 0;
    let lowDensityPercentage = 0;
    let downloadedImages = 0;
    let processedComposites = 0;
    let summary = null;
    const outputFiles: string[] = [];
    
    // Check if vegetation analysis directory exists
    if (await fs.access(vegAnalysisDir).then(() => true).catch(() => false)) {
      try {
        // Read the enhanced summary file
        const summaryPath = path.join(vegAnalysisDir, 'vegetation_analysis_summary.json');
        if (await fs.access(summaryPath).then(() => true).catch(() => false)) {
          const summaryContent = await fs.readFile(summaryPath, 'utf-8');
          summary = JSON.parse(summaryContent);
          
          // Extract enhanced data
          vegetationPercentage = summary.vegetation_percentage || 0;
          highDensityPercentage = summary.high_density_percentage || 0;
          mediumDensityPercentage = summary.medium_density_percentage || 0;
          lowDensityPercentage = summary.low_density_percentage || 0;
          downloadedImages = summary.images_found || 0;
          processedComposites = summary.images_processed || 0;
          
          console.log(`Read enhanced summary: ${vegetationPercentage.toFixed(1)}% vegetation`);
          console.log(`  High density: ${highDensityPercentage.toFixed(1)}%`);
          console.log(`  Medium density: ${mediumDensityPercentage.toFixed(1)}%`);
          console.log(`  Low density: ${lowDensityPercentage.toFixed(1)}%`);
          console.log(`  Images: ${downloadedImages} found, ${processedComposites} processed`);
          
          // Log geographic bounds if available
          if (summary.geographic_bounds) {
            console.log(`  Geographic bounds: ${JSON.stringify(summary.geographic_bounds)}`);
          }
          
          // Log processing config if available
          if (summary.processing_config) {
            console.log(`  Processing config: NDVI threshold ${summary.processing_config.ndvi_threshold}, Cloud threshold ${summary.processing_config.cloud_threshold}%`);
          }
        }
        
        // Collect all output files including new enhanced formats
        const vegFiles = await fs.readdir(vegAnalysisDir);
        console.log(`Found vegetation files: ${vegFiles}`);
        
        for (const file of vegFiles) {
          if (file.endsWith('.png') || file.endsWith('.jpg') || file.endsWith('.tif')) {
            const filePath = path.join(vegAnalysisDir, file);
            const relativePath = path.relative(path.join(process.cwd(), 'public'), filePath);
            outputFiles.push(relativePath);
            console.log(`Added output file: ${relativePath}`);
          }
        }
        
      } catch (error) {
        console.error('Error reading vegetation analysis:', error);
      }
    } else {
      console.log('Vegetation analysis directory does not exist');
    }

    const results = {
      downloadedImages,
      processedComposites,
      vegetationPercentage,
      highDensityPercentage,
      mediumDensityPercentage,
      lowDensityPercentage,
      outputFiles,
      summary  // Include full summary for enhanced map overlay
    };
    
    console.log('Enhanced results collected:', results);
    return results;
  } catch (error) {
    console.error('Error collecting results:', error);
    return {
      downloadedImages: 0,
      processedComposites: 0,
      vegetationPercentage: 0,
      highDensityPercentage: 0,
      mediumDensityPercentage: 0,
      lowDensityPercentage: 0,
      outputFiles: [],
      summary: null
    };
  }
}

// Processing jobs are now managed through the shared processing store 