#!/bin/bash
set -e

echo "🚀 Building Claudette CLI for PyPI..."

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf dist/ build/ *.egg-info/

# Build the package
echo "🔨 Building package..."
python -m build

# Check the build
echo "🔍 Checking build..."
twine check dist/*

# Show what will be uploaded
echo "📦 Built packages:"
ls -la dist/

echo ""
echo "🚀 Ready to upload to PyPI!"
echo ""
echo "🧪 For testing (recommended first):"
echo "  twine upload --repository testpypi dist/*"
echo "  pip install --index-url https://test.pypi.org/simple/ superset-claudette"
echo ""
echo "🌍 For production:"
echo "  twine upload dist/*"
echo ""
echo "💡 Note: Install dev dependencies first: pip install -e .[dev]"
echo "   And configure PyPI tokens in ~/.pypirc (see PYPI.md)"
