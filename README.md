# DbdSocketsMixer

A CLI that mixes DBD socket attachments with character models.

It can also extract socket attachment definitions from a CustomizationItemDB JSON file.

## [Releases](https://github.com/rizzlesauce/DbdSocketsMixer/releases)

## Getting started
Download the latest EXE from the releases page. Place it in a new directory somewhere on your file system.

Use [UAssetGUI](https://github.com/atenfyr/UAssetGUI) to export a CustomizationItemDB to JSON in the same
directory containing DbdSocketsMixer (Save As -> `.json`). You may want to name it to something related to
the corresponding outfit, character, mod, etc.

Run `DbdSocketsMixer` with no arguments to generate a default settings.yaml file.
You may want to rename this settings file to something related to the corresponding outfit, character, mod, etc.
In the settings file, ensure that `customizationItemDbPath` is pointing to the CustomizationItemDB JSON file
you exported from UAssetGUI.

Run `DbdSocketsMixer [settings filename] --extract` to extract all socket attachments from the data table. By default, this will
place any found attachments in the `attachments/` directory (you can change this directory by changing
`attachmentsDir` path in the settings file).

Edit each attachment definition yaml file created in `attachments/`, ensuring that `attachmentId`
is globally unique (it should not duplicate any other attachment ID for the game).

Run `DbdSocketsMixer [settings filename] --rename` to rename attachment files to match their corresponding attachment IDs.
This is helpful when sharing attachment definitions with other modders.

Edit attachment relations and exclusions, as needed, in the settings file.

Run `DbdSocketsMixer [settings filename] --mix` to mix all exported socket attachments with the base models in the
CustimizationItemDB (ones that have no attachments already). Base models remain unaltered, and a new table row
is added for each permutation of the base model and attachment combinations.
This will generate command results to `<settings filename>-results.yaml` and an updated CustomizationItemDB JSON file to
`<CustomizationItemDB filename>-altered.json`.

Convert the altered JSON file back into the original `CustomizationItemDB.uasset` file using UAssetGUI (Save As -> `.uasset`).

## Compatibility
Compatible with DBD-4.4.2, Unreal Engine 4.25, and UAssetGUI 1.0.2

## CLI usage

Run `DbdSocketsMixer -h` for detailed usage and options.

## Building

For starters, you'll need Python 3. Setup a venv for the project and activate it.
Then, get all the necessary dependencies with `pip install -r requirements.txt`.

To bundle everything into a Windows executable, run `pyinstaller --onefile DbdSocketsMixer.py`.
That will generate a portable EXE at `.\dist\DbdSocketsMixer.exe`.
