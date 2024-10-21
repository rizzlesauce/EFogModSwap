# DbdModSwap

![image](https://github.com/user-attachments/assets/8138cefa-bf80-4b0d-94b9-55d5a2cf00b4)

A DBD mod manager CLI for swapping mods between games, paking mods from lists of cooked assets,
and creating custom character slots by mixing game socket attachments with character models.

It also includes a customized game launcher menu, as well as a tool for extracting socket attachment definitions
from existing customization item databases, and a tool for generating socket attachment definitions
from attachment blueprint game paths.

## [Releases](https://github.com/rizzlesauce/DbdModSwap/releases)

![DbdModSwap walkthrough](https://github.com/user-attachments/assets/6b49c0da-4e28-479d-aa21-5bc53ea09492)

## Getting started

Download the latest EXE from the Releases page. Put it in a folder named DbdModSwap (or whatever
you want to call it).

Run `DbdModSwap.exe` with no arguments (or double click on it from file explorer) to enter the
interactive menu.

The tool has several use cases. Generally, it works by configuring the settings for each use case
and then running the associated menu actions to apply the changes.

Running the `List` action at any time can provide useful information regarding your configuration.
Not only can it generate a settings file and help troubleshoot issues, it also generates a results
file with data that you may want to conveniently copy back into your settings file for certain settings
(such as lists of installed and stored pakchunks and available cooked assets).

### Configure game folder

Configure the path to your game folder by selecting `MoreOptions`, `GameDir` and choosing the
folder in the file browser that opens.

### Configure paking folder

Choose a folder where your pakchunks are stored that are not currently installed in the game,
or use the default. To change this folder, select `MoreOptions`, `PakingDir`.

### Generate settings file

Then, run `List` to generate a settings file and get info on your current configuration. The
settings file comes with inline documentation to describe each setting.

### Chaining menu actions

The menu prompt allows you to combine multiple menu actions together by typing in multiple menu item
numbers or names. When typing a menu item name, you can just type part of the name and it
will match it if it isn't amgiguous.

### Setting auto launch

By default, when you enter the launcher menu, the game will automatically start. To prevent this,
go to the submenu `MoreOptions` and toggle the `AutoLaunch` setting.

## Mod configurations

If you want to quickly swap out different mods between games, check out these settings in the
settings file:
* `modGroups`
* `modConfigs`
* `activeModConfig`

You can define groups of mods and combinations of groups (called configurations). Once configured,
you can quickly set the active mod config for your session by choosing `ActiveModConfig`. For
example, if you wanted to set the mod config, install it, and then launch the game, you could
type `active install launch` in the main menu prompt, and that would chain together these
actions.

## Mod paking

If you want to make pakchunks based on a list of cooked assets from an unreal engine project or
another pakchunk, use the `Pak` action, and check out the settings related to paking, mainly:
* `unrealPakPath` (you'll need `UnrealPak 4.25` for making and unpaking pakchunks)
* `unrealProjectDir` (if you're paking content from a project)
* `srcPakPath` (if you're paking content from an existing pakchunk)
* `destPakNumber` (target pakchunk number)
* `destPakName` (target pakchunk name)
* `destPakAssets` (list of assets to include in pakchunk)

If you want to repak an existing pakchunk, you can leave out `destPakNumber` and `destPakName`, as they
will automatically be read from the source pakchunk filename. When you run `List` after having defined
the source pakchunk path, the tool will list out all the assets in the pakchunk to the results file,
and you can copy and paste that into `destPakAssets` to include all those assets into the target pakchunk.

## Socket attachment mixing

Attachment mixing is all about accessorizing character models with new combinations of existing game
attachments. So, let's say you want to put character A's backpack and character B's necklace on
character C - mixing can make that happen.

Mixing works by modifying CustomizationItemDB assets (custom slots). Typically, you would have a different
CustomizationItemDB for each unique character model or related models (like an outfit).
Perhaps, in the future, the tool would be able to assist in creating a CustomizationItemDB
without you having to make one in unreal engine. But for now, you'll need to use a
CustomizationItemDB from another mod or create one in unreal engine.

For editing CustomizationItemDBs, you'll need [UAssetGUI](https://github.com/atenfyr/UAssetGUI). Put it
anywhere you want and configure the setting `usasetGuiPath` to point to the EXE.

Choose a cooked output folder (or, a pakchunk file or folder) containing a character model or socket attachment
definitions you want to mix. It should contain a `CustomizationItemDB.uasset` file defining custom model slots.
If you're wanting to mix a model from the pakchunk, the CustomizationItemDB will need to have a slot for that
model with zero socket attachments. If it doesn't, one will need to be created in UE4 or edited to remove all
the socket attachments using `UAssetGUI`.

You can either copy the `CustomizationItemDB.uasset` file to your DbdModSwap folder, or
leave it where it is and configure a path to it in the settings.

Edit the settings and ensure that `customizationItemDbPath` is pointing to the `CustomizationItemDB.uasset` file.
This path can be absolute or a game content path relative to the unreal project or source pakchunk that
starts with `/Content/`.

Run `List` and the tool will try to read the `CustomizationItemDB.uasset` and list out information regarding
the included model slots and attachments.

### Extracting attachments

If you want to extract socket attachment definitions from the data table, run `Extract`.
By default, this will write any discovered attachment definitions to the `attachments` folder
(you can configure this folder by editing the `attachmentsDir` setting).

Edit each new attachment definition YAML file to ensure that `attachmentId`
is globally unique (it should not duplicate any other attachment IDs in the game).
You may also add a short, descriptive display name for the attachment (e.g., `Hiking Backpack`).
You can view attachment definition files by opening your DbdModSwap folder
(menu option: `Folder`) and, from there, opening the `attachments` folder.
Some attachments might be duplicates of others, so just delete those.

Once you're done editing the attachment definitions, run `Rename` to have the tool rename
each attachment definition file in a standardized way to match its attachment ID.

### Limiting attachment combinations

By default, the tool will try to create every possible combination of attachments with the target
models. If there are a lot of attachments, this can make an enormous amount of custom slots in the
game.

So, in most cases, you'll want to limit the combinations using exclusion rules. There are many
different kinds of rules, and they can get as sophisticated as you like. See the settings file
section entitled `Attachment mixing preferences` for more information.

Once you have your exclusions defined, run `Mix` to mix all of your socket attachments
with the base models (models with zero attachments) in the `CustimizationItemDB.uasset` file.
Existing slots containing attachments will be removed and new ones will be added according to
the stored attachment definitions and your exclusion rules.

After that, the altered `CustomizationItemDB.uasset` file can be packaged and installed using
the tool.

### Defining socket attachment interactively
Another way you can add attachment definition files to your stack is by running `Create`. It will
prompt you to enter an attachment name, display name, model category, and attachment
blueprint game path (attachment blueprints can be discovered using UModel or similar tools).
Then it creates a basic attachment definition. Assuming that the blueprint path is correct
and that the attachment works on your target model, it should work in the game.

## Compatibility

Compatible with Windows, UAssetGUI 1.0.2, Unreal Engine 4.25, and DBD-4.4.2.

## CLI usage

Run `DbdModSwap.exe -h` for detailed usage and options, or without any arguments to view the menu.

## Building

For starters, you'll need Python 3. Setup a venv for the project and activate it.
Then, download all the dependencies with `pip install -r requirements.txt`.

To bundle everything into a Windows executable, run `pyinstaller --onefile DbdModSwap.py`,
which will generate a portable EXE at `.\dist\DbdModSwap.exe`.
