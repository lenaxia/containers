# Outlook Google Calendar Sync (OGCS) - KASM Container

This container runs Outlook Google Calendar Sync in a web-accessible desktop environment using KasmVNC.

## Features

- Web-based access to OGCS via browser (port 3000)
- Full Wine environment with .NET support
- Persistent configuration in `/config`
- Based on LinuxServer.io's KasmVNC base image

## Usage

### Docker Run

```bash
docker run -d \
  --name=ogcs \
  -p 3000:3000 \
  -v /path/to/config:/config \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=America/Los_Angeles \
  ghcr.io/yourusername/outlookgooglecalendarsync:latest
```

### Docker Compose

```yaml
services:
  ogcs:
    image: ghcr.io/yourusername/outlookgooglecalendarsync:latest
    container_name: ogcs
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=America/Los_Angeles
    volumes:
      - /path/to/config:/config
    ports:
      - 3000:3000
    restart: unless-stopped
```

## Accessing the Application

1. Navigate to `http://localhost:3000` in your web browser
2. Default credentials (if authentication is enabled):
   - Username: `abc`
   - Password: `abc`
3. OGCS will launch automatically in the desktop environment

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| PUID | User ID for file permissions | 1000 |
| PGID | Group ID for file permissions | 1000 |
| TZ | Timezone | UTC |
| CUSTOM_USER | HTTP Basic auth username | abc |
| PASSWORD | HTTP Basic auth password | abc |

### Volumes

- `/config` - Contains OGCS application files, settings, and Wine prefix

## First Run

On first run, the container will:
1. Copy OGCS application files to `/config`
2. Initialize Wine prefix in `/config/wine`
3. Install Wine Mono for .NET support
4. Launch OGCS

All OGCS settings, OAuth tokens, and configuration files will persist in `/config`.

## Updates

To update OGCS:
1. Stop the container
2. Remove or rename the `/config/OutlookGoogleCalendarSync.exe` file
3. Start the container - it will copy the new version from the image

## Technical Details

### Wine Installation

This container uses WineHQ stable from the official Wine repository, providing:
- Full 32-bit and 64-bit Wine support
- Wine Mono for .NET application compatibility
- Better compatibility with Windows applications

### KASM Integration

The container follows LinuxServer.io's KASM base image patterns:
- `root/defaults/autostart` - Defines the application to launch
- `root/custom-cont-init.d/init.sh` - Handles initialization
- No custom entrypoint - uses KASM's init system

### File Structure

```
/app/OGCS/              # Read-only OGCS distribution files
/config/                # Persistent data (OGCS + Wine)
  ├── OutlookGoogleCalendarSync.exe
  ├── *.xml             # OGCS settings
  ├── *.json            # OAuth tokens
  └── wine/             # Wine prefix
```

## Troubleshooting

### OGCS doesn't start
- Check logs: `docker logs ogcs`
- Verify Wine initialized: Check for `/config/wine/system.reg`
- Ensure proper permissions on `/config` volume

### Settings not persisting
- Verify `/config` volume is properly mounted
- Check file ownership matches PUID/PGID

### Wine errors
- Wine Mono installation may take time on first run
- Check logs for Wine initialization errors
- Verify `/config/wine` directory exists and is writable

## Building

```bash
cd apps/outlookgooglecalendarsync
docker buildx bake --load image-local
```

## Version

Current OGCS version: 3.0.0.30

## Links

- [OGCS GitHub](https://github.com/phw198/OutlookGoogleCalendarSync)
- [LinuxServer.io KasmVNC Base](https://github.com/linuxserver/docker-baseimage-kasmvnc)
- [WineHQ](https://www.winehq.org/)