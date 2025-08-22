import { NextResponse } from 'next/server';
import path from 'path';
import { promises as fs } from 'fs';

export async function GET() {
  try {
    const rootCitiesPath = path.join(process.cwd(), '..', 'cities.json');
    // process.cwd() is greenspace-app/, go up two to repo root then cities.json
    const data = await fs.readFile(rootCitiesPath, 'utf-8');
    const cities = JSON.parse(data);
    return NextResponse.json(cities);
  } catch (error) {
    console.error('Error reading root cities.json:', error);
    return NextResponse.json({ error: 'Failed to load cities' }, { status: 500 });
  }
}


