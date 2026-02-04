name: Build and Release

on:
   push:
    branches: [ "feature/check-acc" ]

permissions:
    contents: write

jobs:
   build:
    runs-on: windows-latest   # build exe trên Windows

    steps:
    - name: Checkout code
      uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -r requirements_build.txt
        pip install pyinstaller

    - name: Show Installed Packages
        run: pip list
    
    - name: Build EXE
      shell: pwsh
      run: |
        & '.\build_with_browsers.bat'

    - name: Test EXE 
      shell: pwsh 
      run: | 
        ./dist/main.exe --help

    - name: Zip dist folder
      shell: pwsh
      run: |
        Compress-Archive -Path .\dist\* -DestinationPath .\dist.zip

    - name: Create GitHub Release
      uses: softprops/action-gh-release@v2
      with:
        tag_name: v${{ github.run_number }}
        name: Windows Release v${{ github.run_number }}
        files: |
          dist.zip
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
