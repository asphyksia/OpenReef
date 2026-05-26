#!/bin/bash
# Start Next.js frontend
set -e

cd "$(dirname "$0")/../frontend"

echo "=> Starting frontend on port 3000..."
npm run dev
