# DbdSocketsMixer

<img width="863" alt="image" src="https://github.com/user-attachments/assets/2c9ee26d-4481-4cd1-9937-a02d012b9b89">

A CLI that mixes DBD socket attachment combinations with character models into custom slots.

It can also extract socket attachment definitions from CustomizationItemDB JSON files and
create basic attachment definitions using attachment blueprint paths.

## [Releases](https://github.com/rizzlesauce/DbdSocketsMixer/releases)

## Getting started

Download the latest EXE from the releases page. Put it in a new folder named DbdSocketsMixer (or whatever
you want to name it).

Use [UAssetGUI](https://github.com/atenfyr/UAssetGUI) to export a CustomizationItemDB to JSON in the same
folder containing DbdSocketsMixer.exe (Save As -> `.json`). You may want to name it something related to
the corresponding outfit, character, mod, etc.

Run `DbdSocketsMixer.exe` with no arguments to enter an interactive menu. The commands mentioned in the rest
of this section can either be run using the menu or command arguments.

Next, you'll need a YAML settings file. You can name it anything you like, or stick with the default name.
It might be helpful to name it after a corresponding outfit, character, mod, etc.
Selecting `SettingsFilePath` in the menu (or by adding it as a command argument) allows you to set the target
settings file path. If the file does not exist, it will be created with default content when running various commands.

Run `DbdSocketsMixer.exe [settings filename] --list` (menu option: `List`) to create the settings file and list out all the models from the CustomizationItemDB.

Command results are written to `<settings filename>-results.yaml` after running commands, and can be viewed by
selecting the menu option `Results`.
Similarly, you can edit the settings file by selecting the menu option `EditSettings`.
YAML files can be edited with Notepad or other text editors.

If you named your CustomizationItemDB file something other than `CustomizationItemDB.json`, then you'll need to
edit the settings and ensure that `customizationItemDbPath` is pointing to the CustomizationItemDB JSON file
you exported from UAssetGUI.

Run `DbdSocketsMixer.exe [settings filename] --extract` (menu option: `Extract`) to extract all socket attachments from the data table. By default, this will place any found attachments in the `attachments/` directory (you can change this
by editing `attachmentsDir` in the settings).

Review each attachment definition YAML file created in `attachments/`, ensuring that `attachmentId`
is globally unique (it should not duplicate any other attachment ID for the game).
You may also add a short, descriptive display name for the attachment (e.g., `Hiking Backpack`).
If you left your `attachmentsDir` as the default, you can view attachment definition files by opening the folder
containing your settings file (menu option: `Folder`); then, from there, opening the `attachments` folder.
Some attachments might be duplicates. In that case, delete the duplicate attachment definition files.

Once you're done editing the attachment definitions, run `DbdSocketsMixer.exe [settings filename] --rename`
(menu option: `Rename`) to automatically rename each attachment definition file in a standard way to match its
attachment ID.

Next, edit attachment relations and exclusion rules, as desired, in the settings file (menu option: `EditSettings`)
in order to exclude certain attachment combinations for one, many, or all models.

Run `DbdSocketsMixer.exe [settings filename] --mix` (menu option: `Mix`) to mix all extracted socket attachments
with the base models (models without attachments) in the CustimizationItemDB. Any data table rows with
attachments will be removed and new rows will be added for each permutation of base model and attachment
combination.
The altered CustomizationItemDB JSON file is written to `<CustomizationItemDB filename>-altered.json`.

Convert the altered JSON file back into the original `CustomizationItemDB.uasset` file using UAssetGUI
(Save As -> `.uasset`), repack, and add the pakchunk to the game.

## Compatibility

Compatible with Windows, UAssetGUI 1.0.2, Unreal Engine 4.25, and DBD-4.4.2.

## CLI usage

Run `DbdSocketsMixer.exe -h` for detailed usage and options, or without any arguments to view the menu.

## Building

For starters, you'll need Python 3. Setup a venv for the project and activate it.
Then, download all the dependencies with `pip install -r requirements.txt`.

To bundle everything into a Windows executable, run `pyinstaller --onefile DbdSocketsMixer.py`,
which will generate a portable EXE at `.\dist\DbdSocketsMixer.exe`.
