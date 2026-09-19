#!/bin/sh
# Install or update the Kindle client from a computer that has the Kindle mounted over USB.
# Usage: kindle/install.sh /media/<you>/Kindle <server-hostname>
# STATUS: draft. The maintainer installed with scp over SSH instead; run this and record it.
set -eu
mount="${1:?mount point of the Kindle USB drive}"
server="${2:?hostname of the machine running paperwhite serve}"
here="$(cd "$(dirname "$0")" && pwd)"
[ -d "$mount/documents" ] || { echo "$mount does not look like a Kindle USB drive" >&2; exit 1; }
mkdir -p "$mount/paperwhite/state" "$mount/paperwhite/cache" "$mount/extensions"
cp "$here/paperwhite.sh" "$mount/paperwhite/paperwhite.sh"
if [ ! -f "$mount/paperwhite/config" ]; then
    sed "s/^SERVER_HOST=.*/SERVER_HOST=\"$server\"/" "$here/config.example" > "$mount/paperwhite/config"
    echo "wrote $mount/paperwhite/config with SERVER_HOST=$server"
else
    echo "kept existing $mount/paperwhite/config"
fi
rm -rf "$mount/extensions/paperwhite"
cp -r "$here/extensions/paperwhite" "$mount/extensions/paperwhite"
chmod +x "$mount/paperwhite/paperwhite.sh" "$mount/extensions/paperwhite/bin/"*.sh 2>/dev/null || true
sync
echo "installed; eject the Kindle, open KUAL, Paperwhite Weather, Start dashboard"
