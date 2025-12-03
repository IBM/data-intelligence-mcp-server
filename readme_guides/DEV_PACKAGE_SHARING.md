# Development Package Sharing Guide

This guide explains how to create a development package and share it with colleagues for testing.

## Quick Start

The simplest way to share your development changes:

### Option 1: Build and Share a Wheel File (Recommended)

1. **Build the wheel package:**
   ```bash
   make -f Makefile.local wheel
   ```
   This creates a `.whl` file in the `dist/` directory.

2. **Share the wheel file:**
   - The wheel file will be named something like: `ibm_watsonx_data_intelligence_mcp_server-<version>-py3-none-any.whl`
   - Share it via:
     - Email attachment
     - Cloud storage (Google Drive, Dropbox, etc.)
     - Internal file server
     - Slack/Teams file sharing

3. **Your colleague installs it:**
   ```bash
   pip install ibm_watsonx_data_intelligence_mcp_server-<version>-py3-none-any.whl
   ```
   Or if using `uv`:
   ```bash
   uv pip install ibm_watsonx_data_intelligence_mcp_server-<version>-py3-none-any.whl
   ```

### Option 2: Build Source Distribution (Alternative)

If you prefer to share a source distribution:

1. **Build the source distribution:**
   ```bash
   make -f Makefile.local sdist
   ```
   This creates a `.tar.gz` file in the `dist/` directory.

2. **Share and install:**
   ```bash
   pip install ibm_watsonx_data_intelligence_mcp_server-<version>.tar.gz
   ```

### Option 3: Install Directly from Git (If Repository is Accessible)

If your colleague has access to your git repository:

```bash
pip install git+https://github.com/your-org/data-intelligence-mcp-server.git@your-branch-name
```

Or with `uv`:
```bash
uv pip install git+https://github.com/your-org/data-intelligence-mcp-server.git@your-branch-name
```

### Option 4: Build Both Wheel and Source Distribution

To build both formats:

```bash
make -f Makefile.local dist
```

This creates both `.whl` and `.tar.gz` files in `dist/`.

## Detailed Steps

### Step 1: Update Version (Optional but Recommended)

For development packages, you might want to use a dev version identifier:

1. Edit `pyproject.toml`:
   ```toml
   version = "<version>.dev1"  # or "<version>+dev.20250109"
   ```

2. This helps distinguish dev builds from official releases.

### Step 2: Clean Previous Builds (Optional)

```bash
make -f Makefile.local clean
```

This removes old build artifacts.

### Step 3: Build the Package

Choose one of the following:

- **Wheel only (recommended for sharing):**
  ```bash
  make -f Makefile.local wheel
  ```

- **Source distribution only:**
  ```bash
  make -f Makefile.local sdist
  ```

- **Both formats:**
  ```bash
  make -f Makefile.local dist
  ```

### Step 4: Verify the Package (Optional)

Before sharing, verify the package is valid:

```bash
make -f Makefile.local verify
```

This runs `twine check` to validate the package structure.

### Step 5: Share the Package

The built files are in the `dist/` directory:

```bash
ls -lh dist/
```

Share the appropriate file(s) with your colleague.

## Installation Instructions for Your Colleague

Share these instructions with your colleague:

### Prerequisites

- Python 3.11 or higher
- `pip` or `uv` installed

### Installation Steps

1. **Download the wheel file** you shared with them.

2. **Install the package:**
   
   **Using pip:**
   ```bash
   pip install ibm_watsonx_data_intelligence_mcp_server-<version>-py3-none-any.whl
   ```
   
   **Using uv:**
   ```bash
   uv pip install ibm_watsonx_data_intelligence_mcp_server-<version>-py3-none-any.whl
   ```

3. **Verify installation:**
   ```bash
   pip show ibm-watsonx-data-intelligence-mcp-server
   ```

4. **Test the installation:**
   ```bash
   python -m app.main --help
   ```

### Uninstalling

If they need to uninstall:

```bash
pip uninstall ibm-watsonx-data-intelligence-mcp-server
```

## Troubleshooting

### Issue: "No module named 'app'"

**Solution:** Make sure they installed the package, not just downloaded it. The package must be installed in their Python environment.

### Issue: "Package conflicts with existing installation"

**Solution:** Uninstall the existing version first:
```bash
pip uninstall ibm-watsonx-data-intelligence-mcp-server
pip install <new-wheel-file>
```

### Issue: "Wheel file not found"

**Solution:** Make sure they're in the correct directory where the wheel file is located, or provide the full path:
```bash
pip install /path/to/ibm_watsonx_data_intelligence_mcp_server-<version>-py3-none-any.whl
```

## Best Practices

1. **Version Naming:** Use dev version identifiers (e.g., `<version>.dev1`) to avoid conflicts with official releases.

2. **Document Changes:** Include a brief note about what changes are in this dev build.

3. **Test Before Sharing:** Run tests locally before building:
   ```bash
   make -f Makefile.local test
   ```

4. **Clean Build:** Always clean before building a new package:
   ```bash
   make -f Makefile.local clean && make -f Makefile.local wheel
   ```

5. **Verify Package:** Use `make -f Makefile.local verify` to check the package before sharing.

## Quick Reference

| Command | Description |
|---------|-------------|
| `make -f Makefile.local clean` | Remove build artifacts |
| `make -f Makefile.local wheel` | Build wheel package |
| `make -f Makefile.local sdist` | Build source distribution |
| `make -f Makefile.local dist` | Build both wheel and sdist |
| `make -f Makefile.local verify` | Verify package validity |
| `make -f Makefile.local install-local` | Build and install locally for testing |

## Example Workflow

```bash
# 1. Clean previous builds
make -f Makefile.local clean

# 2. Update version in pyproject.toml (optional)
# Edit: version = "<version>.dev1"

# 3. Build the wheel
make -f Makefile.local wheel

# 4. Verify the package
make -f Makefile.local verify

# 5. Share dist/*.whl with your colleague
```

Your colleague then:
```bash
# Install the shared wheel
pip install ibm_watsonx_data_intelligence_mcp_server-<version>.dev1-py3-none-any.whl

# Test it
python -m app.main --help
```

