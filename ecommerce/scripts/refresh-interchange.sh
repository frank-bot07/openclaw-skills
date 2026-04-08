#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/../"
node -e "
import { getDb } from './src/db.js';
import { generateInterchange } from './src/interchange.js';
const db = getDb();
await generateInterchange(db);
console.log('Interchange refreshed');
"