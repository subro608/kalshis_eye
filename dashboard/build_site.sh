#!/bin/bash
# Assemble the password-protected Vercel site (clips build) into $1 (must be OUTSIDE any git repo).
set -e
OUT=${1:?out dir}; ROOT=/scratch/sd5963/kalsi_palantir; USER_NAME=${DASH_USER:-kalshi}
PASS=$(cat /scratch/sd5963/.secrets/kalshi_dashboard_pass)
mkdir -p "$OUT"
$ROOT/.venv/bin/python $ROOT/dashboard/make_clips.py $ROOT/deploy_build
cp -r $ROOT/deploy_build/clips "$OUT/"
cp $ROOT/dashboard/index.html "$OUT/index.html"
CLIPS_JSON=$ROOT/deploy_build/clips.json DATA_OUT="$OUT/data.js" $ROOT/.venv/bin/python $ROOT/dashboard/build_data.py
HASH=$(printf '%s' "$USER_NAME:$PASS" | sha256sum | cut -d' ' -f1)
cat > "$OUT/middleware.js" <<JS
// Basic-auth gate for every path (page, data, clips). Only a SHA-256 of "user:pass" is stored.
export const config = { matcher: '/:path*' };
const H = '$HASH';
async function sha(s){ const b=await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s)); return [...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,'0')).join(''); }
export default async function middleware(request){
  const a = request.headers.get('authorization') || '';
  if (a.startsWith('Basic ')) { try { if (await sha(atob(a.slice(6))) === H) return; } catch (e) {} }
  return new Response('Authentication required', { status: 401, headers: { 'WWW-Authenticate': 'Basic realm="Midterm Night Ops", charset="UTF-8"', 'Cache-Control': 'no-store' } });
}
JS
# cache-bust: page always revalidates; data.js is referenced with a content hash
V=$(sha256sum "$OUT/data.js" | cut -c1-10)
sed -i "s|<script src=\"data.js[^\"]*\"></script>|<script src=\"data.js?v=$V\"></script>|" "$OUT/index.html"
cat > "$OUT/vercel.json" <<JS
{ "headers": [
  { "source": "/(.*)", "headers": [ { "key": "X-Robots-Tag", "value": "noindex, nofollow" }, { "key": "Cache-Control", "value": "private, no-cache" } ] },
  { "source": "/clips/(.*)", "headers": [ { "key": "Cache-Control", "value": "private, max-age=86400" } ] }
] }
JS
du -sh "$OUT"; ls "$OUT"
