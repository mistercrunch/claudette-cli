# PyPI Publishing Guide

## Quick Setup

1. **Install dependencies**: The `pypi-push.sh` script will install `build` and `twine` automatically

2. **Configure PyPI credentials** (one-time setup):
   ```bash
   # Get API tokens from:
   # - Test PyPI: https://test.pypi.org/manage/account/token/
   # - Real PyPI: https://pypi.org/manage/account/token/

   # Create ~/.pypirc
   cat > ~/.pypirc << 'EOF'
   [distutils]
   index-servers = pypi testpypi

   [pypi]
   username = __token__
   password = pypi-YOUR_API_TOKEN_HERE

   [testpypi]
   repository = https://test.pypi.org/legacy/
   username = __token__
   password = pypi-YOUR_TEST_API_TOKEN_HERE
   EOF

   chmod 600 ~/.pypirc
   ```

## Publishing Workflow

1. **Tag the release**:
   ```bash
   git tag v0.1.1
   git push --tags
   ```

2. **Build and test**:
   ```bash
   ./pypi-push.sh
   ```

3. **Test upload** (recommended):
   ```bash
   twine upload --repository testpypi dist/*

   # Test install
   pip install --index-url https://test.pypi.org/simple/ superset-claudette
   ```

4. **Production upload**:
   ```bash
   twine upload dist/*
   ```

## Version Management

Versions are automatically derived from git tags using `hatch-vcs`. Follow [semantic versioning](https://semver.org/):

### Release Process
1. **Tag a release**:
   ```bash
   git tag v0.1.1    # patch: bug fixes
   git tag v0.2.0    # minor: new features
   git tag v1.0.0    # major: breaking changes
   git push --tags
   ```

2. **Version patterns**:
   - On tagged commit: `v0.1.0` → version `0.1.0`
   - Between tags: `v0.1.0` + 3 commits → version `0.1.1.dev3+g<hash>`
   - Dirty working tree: adds `.d<date>` suffix

## Package Info

- **Package name**: `superset-claudette`
- **CLI commands**: `claudette` and `clo`
- **Repository**: GitHub (update URLs in pyproject.toml)
- **License**: Apache-2.0
