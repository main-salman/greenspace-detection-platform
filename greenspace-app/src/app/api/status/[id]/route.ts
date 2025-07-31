import { NextRequest, NextResponse } from 'next/server';
import { getProcessingJob, getAllProcessingJobIds } from '@/lib/processing-store';

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const processingId = params.id;
    console.log(`Status request for ID: ${processingId}`);
    console.log(`Available job IDs: ${getAllProcessingJobIds().join(', ')}`);
    
    const status = getProcessingJob(processingId);

    if (!status) {
      console.log(`Processing job ${processingId} not found`);
      return NextResponse.json(
        { error: 'Processing job not found' },
        { status: 404 }
      );
    }

    console.log(`Returning status for ${processingId}:`, status);
    return NextResponse.json(status);
  } catch (error) {
    console.error('Error getting status:', error);
    return NextResponse.json(
      { error: 'Failed to get processing status' },
      { status: 500 }
    );
  }
} 