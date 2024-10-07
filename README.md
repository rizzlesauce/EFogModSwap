# DbdSocketsMixer

A CLI that mixes DBD socket attachments with character models.

It can also extract socket attachment definitions from a CustomizationItemDB.json file.

## How to use it

Use [UAssetGUI](https://github.com/atenfyr/UAssetGUI) to export a CustomizationItemDB to JSON (Save As -> `.json`).
In your DbdSocketsMixer YAML settings file, set the path to the CustomizationItemDB.json input file and
configure other mixing options.
Run `DbdSocketsMixer <settingsFile.json> --mix`.
Then, convert the output JSON file back into the original CustomizationItemDB.uasset file using UAssetGUI (Save As -> `.uasset`).

Compatible with DBD-4.4.2, Unreal Engine 4.25, and UAssetGUI 1.0.2

## [Releases](https://github.com/rizzlesauce/DbdSocketsMixer/releases)

## Usage

Run `DbdSocketsMixer -h` for detailed usage and options.

## Building

For starters, you'll need Python 3. Setup a venv for the project and activate it.
Then, get all the necessary dependencies with `pip install -r requirements.txt`.

To bundle everything into a Windows executable, run `pyinstaller --onefile DbdSocketsMixer.py`.
That will generate the portable exe at `.\dist\DbdSocketsMixer.exe`.
