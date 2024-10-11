# DbdSocketsMixer

<img width="863" alt="image" src="https://github.com/user-attachments/assets/2c9ee26d-4481-4cd1-9937-a02d012b9b89">

A CLI that mixes DBD socket attachment combinations with character models into custom slots.

It can also extract socket attachment definitions from CustomizationItemDB files and
create basic attachment definitions using attachment blueprint paths.

## [Releases](https://github.com/rizzlesauce/DbdSocketsMixer/releases)

## Getting started

Download the latest EXE from the releases page. Put it in a new folder named DbdSocketsMixer (or whatever
you want to name it).

Download the latest version of [UAssetGUI](https://github.com/atenfyr/UAssetGUI) and put it in the same
folder you created above (or, somewhere else and you can configure a path to it).

Choose a cooked output folder (or, an unpacked pakchunk) containing a character model or socket attachment
definitions you want to mix. It should contain a `CustomizationItemDB.uasset` file defining custom model slots.
If you're wanting to mix a model from the pakchunk, the CustomizationItemDB will need to have a slot for that
model with zero socket attachments. If it doesn't, one will need to be created in UE4 or edited to remove the
socket attachments using UAssetGUI.

You can either copy the `CustomizationItemDB.uasset` file to your DbdSocketsMixer folder, or
leave it where it is and configure a path to it in the settings.

Run `DbdSocketsMixer.exe` with no arguments to enter the interactive menu. The commands mentioned in the rest
of this section can either be run from the menu or using command line arguments.

Configure the path to UAssetGUI if you didn't put it in the same folder as DbdSocketsMixer.
You can do that via command line `DbdSocketsMixer.exe --uassetGuiPath "<path to exe>"` or
interactively with the menu option `UassetGuiPath`.

Next, establish a settings file via a command line argument `DbdSoketsMixer.exe <settings file path>.yaml`
or interactively with the menu option `SettingsFilePath`. The default path is `settings.yaml`,
but you can use a different path or filename that is more suited to the corresponding outfit, character,
mod, etc., or nest it in an aptly named sub directory.

If the settings file doesn't exist, it will be created upon running any command that relies on settings.
Go ahead and run `DbdSocketsMixer.exe [settings filename] --list` (menu option: `List`) to generate a default
settings file if you have not already done so.

This command will also try to read `./CustomizationItemDB.uasset`. If your `CustomizationItemDB.uasset`
file has a different path, then you'll need to configure it in the settings file.
Use the `EditSettings` menu option to open the settings file in an editor.
YAML files can be edited with Notepad or other text editors.

Edit the settings and ensure that `customizationItemDbPath` is pointing to the `CustomizationItemDB.uasset` file.
Other settings exist that can be ignored for now, and descriptions of each setting is included in comments.

If you want to extract socket attachment definitions from the data table,
run `DbdSocketsMixer.exe [settings filename] --extract` (menu option: `Extract`).
By default, this will write any discovered attachment definitions in the `attachments/` directory
(you can change this folder by editing `attachmentsDir` in the settings file).

Command results are written to `<settings filename>-results.yaml`, and can be viewed by
selecting the menu option `Results`.

If new socket attachment definition files were created in `attachmentsDir`,
edit each attachment definition YAML file to ensure that `attachmentId`
is globally unique (it should not duplicate any other attachment IDs in the game).
You may also add a short, descriptive display name for the attachment (e.g., `Hiking Backpack`).
If you kept your `attachmentsDir` as the default, you can view attachment definition files by opening the folder
containing your settings file (menu option: `Folder`) and, from there, opening the `attachments` folder.
Some attachments might be duplicates, in which case you can just delete them.

Once you're done editing the attachment definitions, run `DbdSocketsMixer.exe [settings filename] --rename`
(menu option: `Rename`) to automatically rename each attachment definition file in a standardized way to
match its attachment ID.

Next, edit attachment relation and exclusion rules, as needed, in the settings file (menu option: `EditSettings`)
in order to exclude attachment combinations you don't want.

Run `DbdSocketsMixer.exe [settings filename] --mix` (menu option: `Mix`) to mix all of your socket attachments
with the base models (models with zero attachments) in the `CustimizationItemDB.uasset` file.
Existing slots containing attachments will be removed and new ones will be added according to
the stored attachment definitions and your exclusion settings.

After that, the altered `CustomizationItemDB.uasset` file can be packaged into a pakchunk.

### Defining socket attachment interactively
Another way you can add attachment definition files to your stack is by running
`DbdSocketsMixer.exe [settings filename] --create` (menu option: `Create`). It will
prompt you to enter an attachment name, display name, model category, and attachment
blueprint game path (attachment blueprints can be discovered using UModel or similar tools).
Then it creates a basic attachment definition. Assuming that the blueprint path is correct
and that the attachment works on your target model, it should work in the game.

## Compatibility

Compatible with Windows, UAssetGUI 1.0.2, Unreal Engine 4.25, and DBD-4.4.2.

## CLI usage

Run `DbdSocketsMixer.exe -h` for detailed usage and options, or without any arguments to view the menu.

## Building

For starters, you'll need Python 3. Setup a venv for the project and activate it.
Then, download all the dependencies with `pip install -r requirements.txt`.

To bundle everything into a Windows executable, run `pyinstaller --onefile DbdSocketsMixer.py`,
which will generate a portable EXE at `.\dist\DbdSocketsMixer.exe`.
