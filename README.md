# DbdSocketsMixer

Shell script to mix DBD socket attachments with character models.

Can also extract socket attachment definitions from a CustomizationItemDB.
A YAML settings file specifies the input CustomizationItemDB file and the mix options.
UAssetGUI can be used to export a CustomizationItemDB.uasset file to JSON.
DbdSocketsMixer reads that JSON file and writes an altered version that can be converted back
to the original uasset file using UAssetGUI.

Compatible with DBD-4.4.2, Unreal Engine 4.25, and UAssetGUI 1.0.2

## Building

For starters, you'll need Python 3. Setup a venv for the project and activate it.
Then, get all the necessary dependencies with `pip install -r requirements.txt`.

To bundle everything into a Windows executable, run `pyinstaller --onefile DbdSocketsMixer.py`.
That will generate the portable exe at `.\dist\DbdSocketsMixer.exe`.

## How to run

Run `DbdSocketsMixer -h` for usage and options.
