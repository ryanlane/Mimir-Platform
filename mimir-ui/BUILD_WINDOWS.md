# Building Mimir UI on Windows (Native - Much Faster!)

## Method 1: PowerShell (Recommended)

1. **Open PowerShell** (Windows key + X, then select "Windows PowerShell" or "Terminal")

2. **Navigate to project:**
   ```powershell
   cd C:\Users\futil\projects\github\mimir-web\mimir-ui
   ```

3. **Install dependencies** (if not already done):
   ```powershell
   npm install
   ```

4. **Build the project:**
   ```powershell
   npm run build
   ```

## Method 2: Command Prompt

1. **Open Command Prompt** (Windows key + R, type `cmd`)

2. **Navigate and build:**
   ```cmd
   cd C:\Users\futil\projects\github\mimir-web\mimir-ui
   npm install
   npm run build
   ```

## Method 3: VS Code Terminal (Change Default Shell)

1. **Open VS Code Terminal** (Ctrl + `)
2. **Click dropdown arrow** next to terminal tabs
3. **Select "Command Prompt"** or **"PowerShell"** instead of WSL
4. **Run build commands:**
   ```
   npm install
   npm run build
   ```

## Performance Comparison

| Method | Typical Build Time |
|--------|-------------------|
| WSL | 2-5 minutes |
| Windows PowerShell | 30-60 seconds |
| Windows CMD | 30-60 seconds |

## Why Windows Native is Faster

- **No filesystem translation** between WSL and Windows
- **Direct access** to Windows filesystem
- **Better I/O performance** for Node.js operations
- **No virtualization overhead**

## Quick Commands for Copy/Paste

**PowerShell:**
```powershell
cd C:\Users\futil\projects\github\mimir-web\mimir-ui; npm run build
```

**One-liner for future builds:**
```powershell
cd C:\Users\futil\projects\github\mimir-web\mimir-ui && npm run build && echo "Build complete! Files in dist/ folder"
```

## Serving the Built Files

After building, you can serve locally to test:

**PowerShell:**
```powershell
cd C:\Users\futil\projects\github\mimir-web\mimir-ui
npx serve dist -p 3000
```

Then open: http://localhost:3000

## Development Server (Even Faster)

For development with hot-reload:
```powershell
cd C:\Users\futil\projects\github\mimir-web\mimir-ui
npm run dev
```

## Tips

1. **Keep PowerShell open** in the project directory for quick rebuilds
2. **Use npm scripts** - they're already configured in package.json
3. **File watching** - `npm run dev` automatically rebuilds on changes
4. **Clear cache** if issues: `npm run build -- --force`

## Troubleshooting

If you get permission errors:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

If Node.js/npm not found:
- Install Node.js from: https://nodejs.org/
- Restart PowerShell after installation
