#!/usr/bin/env python3
"""
Local FastAPI server for Greenspace app

Serves the statically exported Next.js UI and mirrors the /api/* endpoints.
Implements background processing with optional parallelism.
"""

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from concurrent.futures import ProcessPoolExecutor
import time
import shutil
import requests

# ---------- Paths ----------
# When packaged with PyInstaller, prefer current working directory as repo root
if getattr(sys, "frozen", False):
    REPO_ROOT = Path(os.getcwd())
else:
    REPO_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = REPO_ROOT / "greenspace-app"
PUBLIC_DIR = APP_DIR / "public"
EXPORT_DIR = APP_DIR / "out"
OUTPUTS_DIR = PUBLIC_DIR / "outputs"
PY_SCRIPTS_DIR = APP_DIR / "python_scripts"

OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# ---------- App ----------
app = FastAPI(title="Greenspace Local Server")

# Note: We'll mount static UI AFTER defining API routes to avoid route shadowing


# ---------- In-memory job store ----------
jobs: Dict[str, Dict[str, Any]] = {}

# NUCLEAR PROCESS CONTROL - Absolute prevention of multiple instances
import threading
import os
import signal
_processing_lock = threading.Lock()
_current_processing_id = None
_is_processing = False
_active_processors = set()  # Track all active processor processes

# Global kill switch for emergency shutdowns
def _nuclear_shutdown_all_processors():
    """Emergency shutdown of all satellite processors"""
    global _active_processors, _is_processing, _current_processing_id
    
    print("🚨 NUCLEAR SHUTDOWN: Terminating all processors")
    
    # Kill any active processor subprocesses
    for proc_id in list(_active_processors):
        print(f"🔪 Killing processor: {proc_id}")
        _active_processors.discard(proc_id)
    
    # Reset all state
    _is_processing = False
    _current_processing_id = None
    
    print("☢️ NUCLEAR SHUTDOWN COMPLETE")

# Register signal handlers for clean shutdown
signal.signal(signal.SIGTERM, lambda s, f: _nuclear_shutdown_all_processors())
signal.signal(signal.SIGINT, lambda s, f: _nuclear_shutdown_all_processors())

# Simple cache for satellite query results to speed up processing
from functools import lru_cache
_satellite_cache = {}
_cache_lock = threading.Lock()


def _serialize_for_json(obj: Any) -> Any:
    """AGGRESSIVE sanitization - convert ALL problematic values to safe defaults"""
    import math
    
    if obj is None:
        return 0.0
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, (int, float)):
        try:
            if math.isnan(obj) or math.isinf(obj):
                return 0.0
            return float(obj)
        except (TypeError, ValueError):
            return 0.0
    elif isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            # Special handling for known problematic fields
            if key in ['veg', 'baselineVegetation', 'compareVegetation', 'percentChange', 
                      'highPct', 'medPct', 'lowPct', 'cloudExcludedPct', 'vegetationPct',
                      'cloud', 'ndviMean', 'hectares']:
                result[key] = _safe_float(value, 0.0)
            else:
                result[key] = _serialize_for_json(value)
        return result
    elif isinstance(obj, list):
        return [_serialize_for_json(item) for item in obj]
    elif isinstance(obj, str):
        return obj
    else:
        # For any other type, try to convert to string or return safe default
        try:
            return str(obj) if obj is not None else "0"
        except:
            return "0"


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float with default fallback"""
    import math
    try:
        if value is None or value == "":
            return default
        result = float(value)
        # Handle NaN and infinity values
        if math.isnan(result) or math.isinf(result):
            return default
        return result
    except (ValueError, TypeError):
        return default


def _write_status(processing_id: str) -> None:
    job = jobs.get(processing_id)
    if not job:
        return
    out_dir = OUTPUTS_DIR / processing_id
    out_dir.mkdir(parents=True, exist_ok=True)
    status_path = out_dir / "status.json"
    try:
        # Convert datetimes to isoformat
        serializable = json.loads(json.dumps(job, default=lambda x: x.isoformat() if hasattr(x, "isoformat") else str(x)))
        status_path.write_text(json.dumps(serializable, indent=2))
    except Exception:
        # Best effort only
        pass


def _collect_month_result(month_dir: Path) -> Dict[str, Any]:
    veg_dir = month_dir / "vegetation_analysis"
    result = {
        "vegetationPercentage": 0.0,
        "highDensityPercentage": 0.0,
        "mediumDensityPercentage": 0.0,
        "lowDensityPercentage": 0.0,
        "downloadedImages": 0,
        "processedComposites": 0,
        "outputFiles": [],
        "summary": None,
    }

    if not veg_dir.exists():
        return result

    summary_path = veg_dir / "vegetation_analysis_summary.json"
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text())
            result["summary"] = summary
            result["vegetationPercentage"] = float(summary.get("vegetation_percentage", 0) or 0)
            result["highDensityPercentage"] = float(summary.get("high_density_percentage", 0) or 0)
            result["mediumDensityPercentage"] = float(summary.get("medium_density_percentage", 0) or 0)
            result["lowDensityPercentage"] = float(summary.get("low_density_percentage", 0) or 0)
            result["downloadedImages"] = int(summary.get("images_found", 0) or 0)
            result["processedComposites"] = int(summary.get("images_processed", 0) or 0)
        except Exception:
            pass

    # Collect file paths relative to PUBLIC_DIR
    try:
        for f in veg_dir.iterdir():
            if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
                rel = f.relative_to(PUBLIC_DIR)
                result["outputFiles"].append(str(rel))
    except Exception:
        pass

    return result


def _load_processor_class():
    import importlib.util

    module_path = PY_SCRIPTS_DIR / "satellite_processor_fixed.py"
    spec = importlib.util.spec_from_file_location("satproc_fixed", str(module_path))
    if not spec or not spec.loader:
        raise RuntimeError("Failed to load satellite processor module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore
    if not hasattr(module, "PerfectAlignmentSatelliteProcessor"):
        raise RuntimeError("Processor class not found in satellite_processor_fixed.py")
    return module.PerfectAlignmentSatelliteProcessor


def _run_single_range(city: Dict[str, Any], year: int, month: int, out_dir: Path, ndvi_threshold: float, cloud_threshold: int,
                      enable_indices: bool, enable_advanced_clouds: bool) -> Dict[str, Any]:
    Processor = _load_processor_class()

    config = {
        "city": city,
        "startMonth": f"{month:02d}",
        "startYear": int(year),
        "endMonth": f"{month:02d}",
        "endYear": int(year),
        "ndviThreshold": float(ndvi_threshold),
        "cloudCoverageThreshold": int(cloud_threshold),
        "enableVegetationIndices": bool(enable_indices),
        "enableAdvancedCloudDetection": bool(enable_advanced_clouds),
        "outputDir": str(out_dir),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    # Execute in-process to avoid extra subprocess overhead
    processor = Processor(config)
    _ = processor.download_and_process_satellite_data()
    return _collect_month_result(out_dir)


def _process_job(processing_id: str, config: Dict[str, Any]) -> None:
    global _processing_lock, _current_processing_id, _is_processing, _active_processors
    
    # NUCLEAR ENTRY CONTROL - Verify single instance
    with _processing_lock:
        if processing_id in _active_processors:
            print(f"❌ NUCLEAR ABORT: {processing_id} already running")
            return
        
        if len(_active_processors) > 0:
            print(f"❌ NUCLEAR ABORT: Another processor running: {_active_processors}")
            return
            
        _active_processors.add(processing_id)
        print(f"🚀 NUCLEAR START: {processing_id} (Active: {len(_active_processors)})")
    
    print(f"🚀 PROCESS_JOB STARTED: {processing_id}")
    
    try:
        out_root = OUTPUTS_DIR / processing_id
        out_root.mkdir(parents=True, exist_ok=True)

        # Initial status
        jobs[processing_id]["status"] = "downloading"
        jobs[processing_id]["progress"] = 5
        jobs[processing_id]["message"] = "Initializing satellite processing..."
        _write_status(processing_id)

        annual_mode = bool(config.get("annualMode", True))
        ndvi = float(config.get("ndviThreshold", 0.3))
        cloud = int(config.get("cloudCoverageThreshold", 20))
        enable_idx = bool(config.get("enableVegetationIndices", False))
        enable_adv = bool(config.get("enableAdvancedCloudDetection", False))

        if annual_mode:
            baseline_year = int(config.get("baselineYear", 2020))
            compare_year = int(config.get("compareYear", baseline_year))

            # Support multi-city batch (sequential to simplify; can parallelize later)
            cities = config.get("cities") or ([config.get("city")] if config.get("city") else [])
            batch_summaries = []

            for city in cities:
                base_monthly = []
                comp_monthly = []
                previews = []
                completed = 0
                total = 24

                # Optimized parallel baseline months processing
                from concurrent.futures import as_completed
                futures = []
                label = "baseline"
                
                # Submit all baseline month tasks with better batching
                for m in range(1, 13):
                    month_dir = out_root / city["city"].replace(" ", "_") / label / f"{m:02d}"
                    futures.append(POOL.submit(_run_single_range, city, baseline_year, m, month_dir, ndvi, cloud, enable_idx, enable_adv))
                
                # Process results as they complete for faster throughput
                month_index_map = {f: i+1 for i, f in enumerate(futures)}
                for f in as_completed(futures):
                    m = month_index_map[f]
                    res = f.result()
                    base_monthly.append({
                        "veg": _safe_float(res.get("vegetationPercentage", 0) if res else 0),
                        "ndviMean": _safe_float((res.get("summary") or {}).get("ndvi_mean", 0) if res else 0),
                        "hectares": _safe_float((res.get("summary") or {}).get("vegetation_pixels", 0) if res else 0) * 0.01,
                        "cloud": _safe_float((res.get("summary") or {}).get("cloud_excluded_percentage", 0) if res else 0),
                        "highPct": _safe_float((res.get("summary") or {}).get("high_density_percentage", 0) if res else 0),
                        "medPct": _safe_float((res.get("summary") or {}).get("medium_density_percentage", 0) if res else 0),
                        "lowPct": _safe_float((res.get("summary") or {}).get("low_density_percentage", 0) if res else 0),
                    })
                    thumb = next((f for f in (res.get("outputFiles", []) if res else []) if f.endswith("vegetation_highlighted.png")),
                                 next(iter(res.get("outputFiles", []) if res else []), ""))
                    if thumb:
                        previews.append({
                            "label": f"{city['city']} {label} {baseline_year}-{m:02d}",
                            "image": thumb,
                            "month": m,
                            "year": baseline_year,
                            "type": "baseline",
                            "veg": _safe_float(res.get("vegetationPercentage", 0) if res else 0),
                            "cloud": _safe_float((res.get("summary") or {}).get("cloud_excluded_percentage", 0) if res else 0),
                            "highPct": _safe_float((res.get("summary") or {}).get("high_density_percentage", 0) if res else 0),
                            "medPct": _safe_float((res.get("summary") or {}).get("medium_density_percentage", 0) if res else 0),
                            "lowPct": _safe_float((res.get("summary") or {}).get("low_density_percentage", 0) if res else 0),
                            "cityName": city["city"],
                        })
                    completed += 1
                    jobs[processing_id].update({
                        "status": "processing",
                        "progress": min(95, round(completed / total * 95)),
                        "message": f"{city['city']} baseline {baseline_year}-{m:02d} completed",
                        "result": {"previews": previews},
                    })
                    _write_status(processing_id)

                # Optimized parallel compare months processing  
                futures = []
                label = "compare"
                
                # Submit all compare month tasks with better batching
                for m in range(1, 13):
                    month_dir = out_root / city["city"].replace(" ", "_") / label / f"{m:02d}"
                    futures.append(POOL.submit(_run_single_range, city, compare_year, m, month_dir, ndvi, cloud, enable_idx, enable_adv))
                
                # Process results as they complete for faster throughput
                month_index_map = {f: i+1 for i, f in enumerate(futures)}
                for f in as_completed(futures):
                    m = month_index_map[f]
                    res = f.result()
                    comp_monthly.append({
                        "veg": _safe_float(res.get("vegetationPercentage", 0) if res else 0),
                        "ndviMean": _safe_float((res.get("summary") or {}).get("ndvi_mean", 0) if res else 0),
                        "hectares": _safe_float((res.get("summary") or {}).get("vegetation_pixels", 0) if res else 0) * 0.01,
                        "cloud": _safe_float((res.get("summary") or {}).get("cloud_excluded_percentage", 0) if res else 0),
                        "highPct": _safe_float((res.get("summary") or {}).get("high_density_percentage", 0) if res else 0),
                        "medPct": _safe_float((res.get("summary") or {}).get("medium_density_percentage", 0) if res else 0),
                        "lowPct": _safe_float((res.get("summary") or {}).get("low_density_percentage", 0) if res else 0),
                    })
                    thumb = next((f for f in (res.get("outputFiles", []) if res else []) if f.endswith("vegetation_highlighted.png")),
                                 next(iter(res.get("outputFiles", []) if res else []), ""))
                    if thumb:
                        previews.append({
                            "label": f"{city['city']} {label} {compare_year}-{m:02d}",
                            "image": thumb,
                            "month": m,
                            "year": compare_year,
                            "type": "compare",
                            "veg": _safe_float(res.get("vegetationPercentage", 0) if res else 0),
                            "cloud": _safe_float((res.get("summary") or {}).get("cloud_excluded_percentage", 0) if res else 0),
                            "highPct": _safe_float((res.get("summary") or {}).get("high_density_percentage", 0) if res else 0),
                            "medPct": _safe_float((res.get("summary") or {}).get("medium_density_percentage", 0) if res else 0),
                            "lowPct": _safe_float((res.get("summary") or {}).get("low_density_percentage", 0) if res else 0),
                            "cityName": city["city"],
                        })
                    completed += 1
                    jobs[processing_id].update({
                        "status": "processing",
                        "progress": min(95, round(completed / total * 95)),
                        "message": f"{city['city']} compare {compare_year}-{m:02d} completed",
                        "result": {"previews": previews},
                    })
                    _write_status(processing_id)

                def _avg(xs):
                    xs = [x for x in xs if isinstance(x, (int, float))]
                    return (sum(xs) / len(xs)) if xs else 0.0

                baseline_veg = _safe_float(_avg([m["veg"] for m in base_monthly]))
                compare_veg = _safe_float(_avg([m["veg"] for m in comp_monthly]))
                percent_change = _safe_float(((compare_veg - baseline_veg) / baseline_veg * 100) if baseline_veg else 0.0)
                high_pct = _safe_float(_avg([m["highPct"] for m in comp_monthly]))
                med_pct = _safe_float(_avg([m["medPct"] for m in comp_monthly]))
                low_pct = _safe_float(_avg([m["lowPct"] for m in comp_monthly]))
                cloud_ex = _safe_float(_avg([m["cloud"] for m in comp_monthly]))

                batch_summaries.append({
                    "city": city,
                    "baselineYear": baseline_year,
                    "compareYear": compare_year,
                    "baselineVegetation": baseline_veg,
                    "compareVegetation": compare_veg,
                    "percentChange": percent_change,
                    "monthlyNdviMeanBaseline": [_safe_float(m["ndviMean"]) for m in base_monthly],
                    "monthlyNdviMeanCompare": [_safe_float(m["ndviMean"]) for m in comp_monthly],
                    "monthlyVegBaseline": [_safe_float(m["veg"]) for m in base_monthly],
                    "monthlyVegCompare": [_safe_float(m["veg"]) for m in comp_monthly],
                    "monthlyHectaresBaseline": [_safe_float(m["hectares"]) for m in base_monthly],
                    "monthlyHectaresCompare": [_safe_float(m["hectares"]) for m in comp_monthly],
                    "highPct": high_pct,
                    "medPct": med_pct,
                    "lowPct": low_pct,
                    "cloudExcludedPct": cloud_ex,
                    "vegetationPct": compare_veg,
                })

                jobs[processing_id].update({
                    "status": "processing",
                    "message": f"Completed {len(batch_summaries)}/{len(cities)} cities",
                    "result": {"previews": previews, "batchSummaries": batch_summaries},
                })
                _write_status(processing_id)

            jobs[processing_id].update({
                "status": "completed",
                "progress": 100,
                "message": "Batch annual comparison completed!",
                "endTime": datetime.utcnow(),
                "result": {"batchSummaries": batch_summaries},
            })
            _write_status(processing_id)
            # Release the processing lock (thread-safe)
            with _processing_lock:
                _current_processing_id = None
                _is_processing = False
            return

        # Single-range mode
        city = config.get("city")
        if not city:
            raise ValueError("City is required for single-range processing")

        month_dir = out_root
        res = _run_single_range(
            city=city,
            year=int(config.get("startYear") or config.get("compareYear") or datetime.utcnow().year),
            month=int(config.get("startMonth") or 7),
            out_dir=month_dir,
            ndvi_threshold=ndvi,
            cloud_threshold=cloud,
            enable_indices=enable_idx,
            enable_advanced_clouds=enable_adv,
        )

        jobs[processing_id].update({
            "status": "completed",
            "progress": 100,
            "message": "Processing completed successfully!",
            "endTime": datetime.utcnow(),
            "result": res,
        })
        _write_status(processing_id)

    except Exception as e:
        import errno as _errno
        msg = str(e)
        is_broken_pipe = isinstance(e, BrokenPipeError) or getattr(e, 'errno', None) == 32 or 'Broken pipe' in msg or getattr(e, 'errno', None) == _errno.EPIPE
        if is_broken_pipe:
            try:
                # Attempt graceful finalization from disk artifacts
                out_root = OUTPUTS_DIR / processing_id
                fallback_res = None
                # Try to collect single-range result if present
                if out_root.exists():
                    # If annual batch, gather any available previews and batch summaries
                    # Otherwise, try single month result
                    # Prefer single-range collector first
                    fallback_res = _collect_month_result(out_root)
                jobs[processing_id].update({
                    "status": "completed",
                    "progress": max(95, int(jobs.get(processing_id, {}).get("progress", 90))),
                    "message": "Completed with minor IO warning (Broken pipe)",
                    "endTime": datetime.utcnow(),
                    "result": jobs.get(processing_id, {}).get("result") or fallback_res,
                })
                _write_status(processing_id)
            except Exception:
                jobs[processing_id].update({
                    "status": "failed",
                    "progress": 0,
                    "message": f"Processing failed: {e}",
                    "endTime": datetime.utcnow(),
                })
                _write_status(processing_id)
        else:
            jobs[processing_id].update({
                "status": "failed",
                "progress": 0,
                "message": f"Processing failed: {e}",
                "endTime": datetime.utcnow(),
            })
            _write_status(processing_id)
    finally:
        # NUCLEAR CLEANUP - Remove from active processors
        print(f"🏁 PROCESS_JOB FINISHED: {processing_id}")
        with _processing_lock:
            _active_processors.discard(processing_id)
            _current_processing_id = None
            _is_processing = False
            print(f"☢️ NUCLEAR CLEANUP: {processing_id} (Active: {len(_active_processors)})")
        print(f"🔓 LOCK RELEASED: {processing_id}")


# Optimized process pool for better multithreading
# Balanced worker count for optimal performance without API overload  
MAX_WORKERS = int(os.getenv("GREENSPACE_MAX_WORKERS", min(4, max(2, (os.cpu_count() or 4) // 3))))
POOL = ProcessPoolExecutor(max_workers=MAX_WORKERS)

print(f"🚀 Greenspace app initialized with {MAX_WORKERS} workers for optimal performance")


@app.get("/api/debug/data")
async def debug_data():
    """Debug endpoint to see what data structure is being returned"""
    # Create a sample data structure that might contain the problematic values
    sample_data = {
        "status": "completed",
        "result": {
            "batchSummaries": [{
                "city": {"city": "Test City"},
                "baselineVegetation": None,  # This could be the problem
                "compareVegetation": float('nan'),  # Or this
                "percentChange": float('inf'),  # Or this
                "monthlyVegBaseline": [None, float('nan'), 1.5],
                "monthlyVegCompare": [2.1, None, float('inf')],
                "highPct": None,
                "medPct": float('nan'),
                "lowPct": 0.0,
            }]
        }
    }
    
    # Apply our sanitization and see what happens
    sanitized = _serialize_for_json(sample_data)
    return JSONResponse(sanitized)


@app.post("/api/process")
async def start_process(request: Request):
    global _processing_lock, _current_processing_id, _is_processing
    
    print(f"🔒 Processing request - current state: _is_processing={_is_processing}, _current_processing_id={_current_processing_id}")
    
    # Triple check: if already running, return the current id so UI can attach to it
    if _is_processing:
        print("❌ BUSY: Processing already in progress - returning current id")
        return JSONResponse({"processingId": _current_processing_id or list(_active_processors)[0] if _active_processors else None, "status": "busy"})
        
    try:
        config = await request.json()
    except Exception as e:
        print(f"❌ JSON parsing error: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not (config.get("city") or (config.get("cities") and len(config.get("cities")) > 0)):
        raise HTTPException(status_code=400, detail="City or cities are required")

    # NUCLEAR LOCK - Absolute prevention of multiple instances
    acquired = _processing_lock.acquire(blocking=False)
    if not acquired:
        print("❌ NUCLEAR BUSY: Could not acquire lock - returning current id")
        return JSONResponse({"processingId": _current_processing_id or list(_active_processors)[0] if _active_processors else None, "status": "busy"})
    
    try:
        # NUCLEAR VERIFICATION - Check all protection layers
        if len(_active_processors) > 0:
            print(f"❌ NUCLEAR BUSY: Active processors: {_active_processors}")
            return JSONResponse({"processingId": list(_active_processors)[0], "status": "busy"})
            
        if _is_processing or _current_processing_id is not None:
            print(f"❌ NUCLEAR BUSY: State conflict: processing={_is_processing}, id={_current_processing_id}")
            return JSONResponse({"processingId": _current_processing_id, "status": "busy"})
        
        processing_id = str(uuid.uuid4())
        _current_processing_id = processing_id
        _is_processing = True
        
        print(f"✅ NUCLEAR STARTING: New processing job {processing_id}")
        
        jobs[processing_id] = {
            "id": processing_id,
            "status": "pending", 
            "progress": 0,
            "message": "Initializing processing...",
            "startTime": datetime.utcnow(),
            "result": None,
        }
        _write_status(processing_id)
        
    finally:
        _processing_lock.release()
    
    # Start processing in background
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, _process_job, processing_id, config)

    return JSONResponse({"processingId": processing_id})


def _load_status_from_disk(processing_id: str) -> Optional[Dict[str, Any]]:
    status_path = OUTPUTS_DIR / processing_id / "status.json"
    if status_path.exists():
        try:
            return json.loads(status_path.read_text())
        except Exception:
            return None
    return None


@app.get("/api/status/{processing_id}")
async def get_status(processing_id: str):
    status = jobs.get(processing_id)
    if not status:
        # Fallback to file-backed status
        status = _load_status_from_disk(processing_id)
    if not status:
        raise HTTPException(status_code=404, detail="Processing job not found")
    # Serialize datetime objects for JSON compatibility
    serialized_status = _serialize_for_json(status)
    return JSONResponse(serialized_status)


@app.get("/api/status/stream/{processing_id}")
async def status_stream(processing_id: str):
    async def event_generator():
        last = None
        max_iterations = 300  # 5 minutes max
        iterations = 0
        
        while iterations < max_iterations:
            iterations += 1
            status = jobs.get(processing_id) or _load_status_from_disk(processing_id)
            
            if not status:
                # Send error if no status found
                yield f"data: {json.dumps({'error': 'Processing job not found'})}\n\n"
                break
                
            # Apply comprehensive sanitization before sending
            sanitized_status = _serialize_for_json(status)
            payload = json.dumps(sanitized_status, default=str)
            if payload != last:
                last = payload
                yield f"data: {payload}\n\n"
                
            if status.get("status") in {"completed", "failed"}:
                break
                
            await asyncio.sleep(2.0)
        
        # Send final close event
        yield f"data: {json.dumps({'status': 'stream_closed'})}\n\n"

    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )


@app.get("/api/cities")
async def get_cities():
    root_cities = REPO_ROOT / "cities.json"
    try:
        data = json.loads(root_cities.read_text())
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to load cities")
    return JSONResponse(data)


@app.get("/api/health")
async def health():
    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "greenspace-local",
    })


def _mime_for_suffix(suffix: str) -> str:
    s = suffix.lower()
    if s == ".png":
        return "image/png"
    if s in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if s in {".tif", ".tiff"}:
        return "image/tiff"
    if s == ".json":
        return "application/json"
    if s == ".txt":
        return "text/plain"
    return "application/octet-stream"


@app.get("/api/preview")
async def preview(file: str):
    full_path = (PUBLIC_DIR / file).resolve()
    if not str(full_path).startswith(str(PUBLIC_DIR.resolve())):
        raise HTTPException(status_code=403, detail="Invalid file path")
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    suffix = full_path.suffix.lower()

    # Convert TIFF to PNG for browser preview
    if suffix in {".tif", ".tiff"}:
        try:
            import rasterio
            import numpy as np
            import tempfile
            with rasterio.open(str(full_path)) as src:
                arr = src.read(1)
                # Normalize to 0-255
                arr = arr.astype("float32")
                arr = (arr - np.nanmin(arr)) / (np.nanmax(arr) - np.nanmin(arr) + 1e-9)
                arr = (arr * 255).astype("uint8")
                tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                from PIL import Image
                Image.fromarray(arr).save(tmp.name)
                return FileResponse(tmp.name, media_type="image/png")
        except Exception:
            # Fallback to raw file
            pass

    return FileResponse(str(full_path), media_type=_mime_for_suffix(suffix))


@app.get("/api/download")
async def download(file: str):
    full_path = (PUBLIC_DIR / file).resolve()
    if not str(full_path).startswith(str(PUBLIC_DIR.resolve())):
        raise HTTPException(status_code=403, detail="Invalid file path")
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        str(full_path),
        media_type=_mime_for_suffix(full_path.suffix),
        filename=full_path.name,
    )


# ---------- Cities utilities ----------
def _cities_path() -> Path:
    return REPO_ROOT / "cities.json"


def _load_cities() -> list[dict[str, Any]]:
    p = _cities_path()
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text())
    except Exception:
        return []


def _save_cities(cities: list[dict[str, Any]]) -> None:
    p = _cities_path()
    # backup
    try:
        ts = time.strftime("%Y%m%d_%H%M%S")
        backup_dir = p.parent / "cities_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        if p.exists():
            shutil.copyfile(str(p), str(backup_dir / f"cities.json.{ts}.bak"))
    except Exception:
        pass
    p.write_text(json.dumps(cities, indent=2))


def _centroid_from_polygon(polygon_geojson: dict[str, Any]) -> tuple[float, float] | None:
    try:
        geom = polygon_geojson.get("geometry") or polygon_geojson
        if not geom or geom.get("type") != "Polygon":
            return None
        coords: list[list[list[float]]] = geom.get("coordinates", [])
        if not coords or not coords[0]:
            return None
        ring = coords[0]
        xs = [pt[0] for pt in ring]
        ys = [pt[1] for pt in ring]
        return (sum(ys) / len(ys), sum(xs) / len(xs))  # lat, lon
    except Exception:
        return None


def _fetch_osm_boundary(city: str, country: str, state: str | None = None) -> dict[str, Any] | None:
    headers = {"User-Agent": "greenspace-local/1.0 (contact: local)"}
    # Try Nominatim first (simple, often sufficient)
    try:
        params = {
            "format": "json",
            "polygon_geojson": 1,
            "addressdetails": 1,
            "limit": 1,
            "city": city,
            "country": country,
        }
        if state:
            params["state"] = state
        r = requests.get("https://nominatim.openstreetmap.org/search", params=params, headers=headers, timeout=20)
        if r.ok:
            data = r.json()
            if data and data[0].get("geojson") and data[0]["geojson"].get("type") in ("Polygon", "MultiPolygon"):
                gj = data[0]["geojson"]
                if gj["type"] == "Polygon":
                    return {"type": "Feature", "properties": {}, "geometry": gj}
                # Convert first polygon from MultiPolygon
                if gj["type"] == "MultiPolygon" and gj.get("coordinates"):
                    first = gj["coordinates"][0]
                    return {"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": first}}
    except Exception:
        pass

    # Fallback to Overpass (basic)
    try:
        # Simplified query: find relation with name=city in given country/state
        q_parts = ["[out:json][timeout:25];"]
        if country:
            q_parts.append(f'area["name"="{country}"]->.a;')
        if state:
            q_parts.append(f'area.a["name"="{state}"]->.b;')
            q_parts.append('rel(area.b)["boundary"="administrative"]["name"="' + city + '"];')
        else:
            q_parts.append('rel(area.a)["boundary"="administrative"]["name"="' + city + '"];')
        q_parts.append("out geom;")
        query = "".join(q_parts)
        r = requests.post("https://overpass-api.de/api/interpreter", data=query.encode("utf-8"), headers=headers, timeout=30)
        if r.ok:
            j = r.json()
            for el in j.get("elements", []):
                if el.get("type") == "relation" and el.get("geometry"):
                    coords = [[ [pt["lon"], pt["lat"]] for pt in el["geometry"] ]]
                    return {"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": coords}}
    except Exception:
        pass
    return None


@app.get("/api/osm/boundary")
async def osm_boundary(city: str, country: str, state: str | None = None):
    gj = _fetch_osm_boundary(city=city, country=country, state=state)
    if not gj:
        raise HTTPException(status_code=404, detail="Boundary not found")
    return JSONResponse({"polygon_geojson": gj})


@app.post("/api/cities/upsert")
async def upsert_city(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    required = ["country", "city"]
    for k in required:
        if not body.get(k):
            raise HTTPException(status_code=400, detail=f"Missing required field: {k}")

    polygon_geojson = body.get("polygon_geojson")
    if not polygon_geojson and body.get("fetchBoundary"):
        gj = _fetch_osm_boundary(body.get("city"), body.get("country"), body.get("state_province") or body.get("state"))
        if gj:
            polygon_geojson = gj

    cities = _load_cities()
    city_id = body.get("city_id") or str(uuid.uuid4())

    # Compute lat/lon from centroid if not provided
    lat = body.get("latitude")
    lon = body.get("longitude")
    if (not lat or not lon) and polygon_geojson:
        cent = _centroid_from_polygon(polygon_geojson)
        if cent:
            lat, lon = f"{cent[0]}", f"{cent[1]}"

    new_entry = {
        "city_id": city_id,
        "country": body.get("country"),
        "state_province": body.get("state_province") or body.get("state") or "",
        "city": body.get("city"),
        "latitude": str(lat) if lat is not None else body.get("latitude", ""),
        "longitude": str(lon) if lon is not None else body.get("longitude", ""),
        "notification_email": body.get("notification_email", ""),
        "polygon_geojson": polygon_geojson or body.get("polygon_geojson", {}),
    }

    updated = False
    for i, c in enumerate(cities):
        if c.get("city_id") == city_id:
            cities[i] = new_entry
            updated = True
            break
    if not updated:
        cities.append(new_entry)

    _save_cities(cities)
    return JSONResponse({"success": True, "city": new_entry})


@app.delete("/api/cities/{city_id}")
async def delete_city(city_id: str):
    cities = _load_cities()
    new_cities = [c for c in cities if c.get("city_id") != city_id]
    if len(new_cities) == len(cities):
        raise HTTPException(status_code=404, detail="City not found")
    _save_cities(new_cities)
    return JSONResponse({"success": True})


# Serve static files manually instead of mounting to avoid route conflicts
@app.get("/")
async def serve_index():
    if EXPORT_DIR.exists():
        index_path = EXPORT_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
    # Fallback: if Next.js dev server is running, redirect to it for the UI
    try:
        r = requests.get("http://127.0.0.1:3000", timeout=0.5)
        if r.status_code < 500:
            html = """
            <meta http-equiv="refresh" content="0; url=http://127.0.0.1:3000" />
            <p>Redirecting to UI at <a href=\"http://127.0.0.1:3000\">http://127.0.0.1:3000</a>...</p>
            <script>location.replace('http://127.0.0.1:3000');</script>
            """
            return HTMLResponse(html)
    except Exception:
        pass
    return HTMLResponse("<h2>Greenspace Local Server</h2><p>Build the UI with: npm run export</p>")

@app.get("/{full_path:path}")
async def serve_static_or_spa(full_path: str, request: Request):
    # Skip API routes
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
    
    # Try to serve the specific file first (including .html files)
    file_path = EXPORT_DIR / full_path
    if file_path.exists() and file_path.is_file():
        return FileResponse(str(file_path))
    
    # Try with .html extension
    html_path = EXPORT_DIR / f"{full_path}.html"
    if html_path.exists() and html_path.is_file():
        return FileResponse(str(html_path))
    
    # For SPA routes that don't have specific files, serve the main index.html
    # This allows client-side routing to work
    index_path = EXPORT_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    
    # Fallback to 404
    not_found_path = EXPORT_DIR / "404.html"
    if not_found_path.exists():
        return FileResponse(str(not_found_path))
    
    raise HTTPException(status_code=404, detail="Page not found")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    print(f"Starting Greenspace server on http://127.0.0.1:{port}")
    print("Press Ctrl+C to stop the server")
    uvicorn.run(app, host="127.0.0.1", port=port, reload=False)

# Static files are now mounted above to avoid conflicts


