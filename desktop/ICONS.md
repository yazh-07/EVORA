The application header and favicon use copies of desktop/icon.png and icon.ico in frontend/public/brand.

The backend PE icon/version are configured in evora.spec and backend-version.txt. The desktop PE resources are generated from versioninfo.json and icon.ico:

```sh
cd desktop
go run github.com/josephspurrier/goversioninfo/cmd/goversioninfo@v1.5.0 -64 -o resource_windows_amd64.syso
```

Commit the generated resource so ordinary Windows go build commands embed it. Update both version files and the installer version together when releasing.
