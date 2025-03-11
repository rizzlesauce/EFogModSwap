## EFogModSwap

![image](https://github.com/user-attachments/assets/05100984-5561-4a55-b0aa-275170228435)

An EFog mod manager CLI for swapping mods between games, paking mods from lists of cooked assets,
and creating custom cosmetic slots by mixing game socket attachments with character models.

It also includes a customized game launcher menu, as well as a tool for extracting and cloning socket attachments
from existing customization item databases and blueprint paths, and a search feature for exploring game assets.

## Highlights
* quickly copy accessory blueprints so you can make custom accessories (which can also be full character models with custom bones) that are bone physics capable and also still work with character animations
* configure pakchunk asset lists and quickly (re-)package mods from cooked content (no manual file copying needed to package or recook/repackage a mod)
* conveniently chain actions together ("pak install launch") to quickly (re-)package a mod, install it into the game, and launch the game immediately to test it out
* quickly swap between different mod sets you've configured (e.g., 1v1 vs 1v4)
* search, list, and inspect all game assets, pakchunks, and CustomizationItemDB tables, looking for models, accessories, blueprints, name map entries, etc.
* auto populate CustomizationItemDB slots with accessory combinations you've configured using inclusion and exclusion rules

## [Releases](https://github.com/rizzlesauce/EFogModSwap/releases)

![EFogModSwap walkthrough](https://github.com/user-attachments/assets/6b49c0da-4e28-479d-aa21-5bc53ea09492)

## Menu features

The tool has several use cases. Generally, it works by configuring the settings for each use case
and then running the associated menu actions to apply the changes.

### Using `List`

Running the `List` action at any time can provide useful information regarding your configuration.
Not only can it generate a settings file and help troubleshoot issues, it also generates a results
file with data that you may want to conveniently copy back into your settings file for certain settings
(such as lists of installed and stored pakchunks and available cooked assets).

### Chaining menu actions

The menu prompt allows you to combine multiple menu actions together by typing in multiple menu item
numbers or names. When typing a menu item name, you can just type part of the name and it
will match it if it isn't amgiguous.

## Getting started

Download the latest EXE from the Releases page. Put it in a folder named EFogModSwap (or whatever
you want to call it).

Run `EFogModSwap.exe` with no arguments (or double click on it from file explorer) to enter the
interactive menu.

### Configure game folder and version

Configure the path to your game folder by selecting `MoreOptions`, `GameDir` and choosing the
folder in the file browser that opens. From the same menu, select the `GameVersion`.

### Configure paking folder

Choose a folder where your pakchunks are stored that are not currently installed in the game,
or use the default. To change this folder, select `MoreOptions`, `PakingDir`.

### Generate settings file

Then, run `List` to generate a settings file and get info on your current configuration. The
settings file comes with inline documentation to describe each setting.

### Toggle auto launch

By default, when you enter the launcher menu, the game will automatically start. To prevent this,
go to the submenu `MoreOptions` and toggle the `AutoLaunch` setting. Running `auto` from the
main menu is another quick way of toggling this behavior.

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

## Modding

### Mod paking

If you want to make pakchunks based on a list of cooked assets from an unreal engine project or
another pakchunk, use the `Pak` action, and check out the settings related to paking, mainly:
* `unrealPakPath` (you'll need `UnrealPak` for making and unpaking pakchunks)
* `unrealProjectDir` (if you're paking content from a project)
* `srcPakPath` (if you're paking content from an existing pakchunk)
* `destPakNumber` (target pakchunk number)
* `destPakName` (target pakchunk name)
* `destPakAssets` (list of assets to include in pakchunk)

If you want to repak an existing pakchunk, you can leave out `destPakNumber` and `destPakName`, as they
will automatically be read from the source pakchunk filename. When you run `List` after having defined
the source pakchunk path, the tool will list out all the assets in the pakchunk to the results file,
and you can copy and paste that into `destPakAssets` to include all those assets into the target pakchunk.

### Batching mods

You can run actions on multiple mods at once by batching settings files. To do so, you need a main
settings file that contains a `batch` list, each item being a path to another settings file. Then,
run actions as normal and it will apply to each mod in the batch.
For example, `pak install launch` would package each mod in the batch, then
install any updated mods targeted for installation, and finally launch the game.

### Upgrading mods

To upgrade a mod from one game version to another, use the `Upgrade` action. `prevGameVersion` (upgrading from)
and `gameVersion` (upgrading to) settings need to be configured, as well as `unrealPakPath` and
[uassetGuiPath](https://github.com/atenfyr/UAssetGUI). Currently, upgrading only works on cooked
CustomizationItemDB assets for certain versions (6.5.2 -> 6.7.*). You'll also need to configure one or more
data table assets. The simplest way is to configure `srcPakPath` to the pakchunk of the old version,
and set `customizationItemDbPath` to `/Content/**/CustomizationItemDB`, so that it automatically upgrades
every data table in the pakchunk. Then, run `upgrade pak`, and this will produce an upgraded pakchunk
with the same name in your `pakingDir` folder.

If you want to upgrade multiple pakchunks in sequence, you can run the menu program with additional command line
argument `--srcPakPath <folder containing mods>/*.pak` to specify multiple pakchunks. Then, from the menu,
run `upgrade pak` and confirm that you want to run actions on each pakchunk. Any pakchunk errors will be reported
at the end.

#### Example usage: upgrading a folder of mods from 6.5.2 to 6.7.2
From the command line (powershell), run:
```
.\EFogModSwap.exe --prevGameVersion 6.5.2 --gameVersion 6.7.2 --srcPakPath <path-to-my-6.5.2-mods-folder>\*.pak --customizationItemDbPath /Content/**/CustomizationItemDB
```
Note the slash direction and case sensitivity in the `--customizationItemDbPath` argument.

From the menu:
* Change `Overwrite` to `always`
* Go into `MoreOptions` submenu
  * Configure `UassetGuiPath` to the appropriate tool EXE path
  * Configure `UnrealPakPath` to the appropriate tool EXE path
  * Go `Back` to the main menu
* Type `upgrade pak` and press Enter to run the actions
* Confirm that you want to run actions on each pakchunk by pressing Enter

Upgraded pakchunks will be output in a new folder called `paking-6.7.2`.

### Mixing socket attachments

Attachment mixing is all about accessorizing character models with new combinations of accessories
and model attachments. So, let's say you want to put character A's backpack and character B's necklace on
character C - mixing can make that happen.

Mixing works by modifying CustomizationItemDB assets (custom cosmetic slots). Typically, you would have a different
CustomizationItemDB for each unique character model or related models (like an outfit).
Perhaps, in the future, the tool would be able to assist in creating a CustomizationItemDB
without you having to make one in unreal engine. But for now, you'll need to use a
CustomizationItemDB from another mod or create one in unreal engine.

For editing CustomizationItemDBs, you'll need [UAssetGUI](https://github.com/atenfyr/UAssetGUI). Put it
anywhere you want and configure the setting `uassetGuiPath` to point to the EXE.

Choose a cooked output folder (or, a pakchunk file or folder) containing a character model or socket attachment
definitions you want to mix. It should contain a `CustomizationItemDB.uasset` file defining custom cosmetic slots.
If you're wanting to mix a model from the pakchunk, the CustomizationItemDB will need to have a slot for that
model with zero socket attachments. If it doesn't, one will need to be created or edited in UE4 or `UAssetGUI`
to get a model slot with no attachments on it.

You can either copy the `CustomizationItemDB.uasset` file to your EFogModSwap folder, or
leave it where it is and configure a path to it in the settings.

Edit the settings and ensure that `customizationItemDbPath` is pointing to the `CustomizationItemDB.uasset` file.
This path can be absolute or a game content path (starts with `/Content/`) relative to the unreal project or
source pakchunk. When relative to a source pakchunk, a wildcard can be used (`/Content/**/CustomizationItemDB`).

Run `List` and the tool will try to read the `CustomizationItemDB.uasset` and list out information regarding
the included model slots and attachments.

#### Extracting attachments

If you want to extract socket attachment definitions from CustomizationItemDB entries, run
`Sockets`, `Extract` (pair this with `Search` if you want to search game pak files for
attachments). By default, this will write any discovered attachment definitions to the `attachments`
folder (you can configure this folder by editing the `attachmentsDir` setting).

Edit each new attachment definition YAML file to ensure that `attachmentId`
is globally unique (it should not duplicate any other attachment IDs in the game).
You may also add a short, descriptive display name for the attachment (e.g., `Hiking Backpack`).
You can view attachment definition files by selecting `Folders`, `OpenAttachmentsDir`.
Some attachments might be duplicates of others, so just delete those.

Once you're done editing the attachment definitions, run `Rename` to have the tool rename
each attachment definition file in a standardized way to match its attachment ID.

NOTE: extracted attachments for game version 4.4.2 should also work in 6.5.2, provided that
the blueprint path has not changed.

#### Limiting attachment combinations

By default, the tool will try to create every possible combination of attachments with the target
models. If there are a lot of attachments, this can make an enormous amount of custom cosmetic slots in the
game.

So, in most cases, you'll want to limit the combinations using exclusion rules. There are many
different kinds of rules, and they can get as sophisticated as you like. See the settings file
section entitled `Attachment mixing preferences` for more information.

Once you have your exclusions defined, run `Mix` to mix all of your socket attachments
with the base models (models with zero attachments) in the `CustimizationItemDB.uasset` file.
Existing slots containing attachments will be removed and new ones will be added according to
the stored attachment definitions and your exclusion rules.

After that, the altered `CustomizationItemDB.uasset` file can be packaged (`Pak`) and installed
(`Install`) using the tool.

#### Adding and cloning socket attachments interactively

If you know the path to the attachment blueprint you want to use (using `Umodel`), you can run
the `Sockets`, `Create` action to interactively add or clone an existing attachment to your stack.
If you have `Umodel` and `UassetGUI` configured, it will give you more info on the attachment,
display the attachment in a 3D viewer, and ask you if you want to copy the attachment to a new
blueprint.

It will prompt you to enter an attachment ID, display name, and model category.
Then it creates an attachment definition that can be used for mixing with base models into
attachment combination slots.

##### Cloning attachments to create models with bone physics

Copying an attachment to a new blueprint is how you can create new attachments with
custom meshes, skeletons, and bone physics, which can be used to replace entire character
models while still being compatible with the game's character animations.

Once you've copied an attachment blueprint, you can set up your mesh, skeleton, and physics
assets in Unreal Engine with the paths you specified when copying the blueprint using `Create`.
* for the attachment mesh, you'll want to use a skeleton that matches your character and has all the bones you need for animation and bone based physics
* edit the physics asset to create collision bodies and constraints (I won't get into the details of using the Physics Asset Editor right now)
* create a nearly empty, invisible skeletal mesh as the base model for the mod (your attachment will replace it visually)
* add that base model to your CustomizationItemDB (with no attachments)
* cook your assets
* edit your `destPakAssets` to include all the new assets, including the cloned attachment blueprint and animation blueprint
* edit your attachment exclusion rules to exclude the base model on its own (`combosToSkip`) and to always require the attachment with your base model (`combosRequired`)
* run `mix pak install [launch]` to mix the new attachment with your target base models, install the mod, and optionally launch the game to test it out

### Searching game assets

Using the `Search` action, you can search, visualize, and extract game assets in various ways
(`Umodel` required). Search parameters can be set up in the settings file:
* `searchingSlots` - whether to search CustomizationItemDB entries for models and attachments
* `searchAssetNameMatchers` - asset path search matchers
* `searchNameMapNameMatchers` - asset name map name matchers
* `searchJsonStringMatchers` - UassetGUI asset json matchers
* `searchBinaryAsciiMatchers` - asset binary data ascii matchers
* `searchResume` - details to resume a previous, unfinished search, or to start the search from a specific point

When running search, you can use the keyboard to interactively pause (`p`), toggle
visualizations (`v`), toggle searching slots (`s`), or quit the search (`q`).

## Compatibility

Compatible with:
* Windows
* EFog:
  * 4.4.2
  * 6.5.2
  * 6.7.* (*not fully tested)
* Cooked assets, UnrealPak, and Umodel for Unreal Engine versions:
  * 4.25
  * 4.27
* UAssetGUI 1.0.2

## CLI usage

Run `EFogModSwap.exe -h` for detailed usage and options, or without any arguments to view the menu.

## Building

For starters, you'll need Python 3. Set up a venv for the project and activate it.
Then, download all the dependencies with `pip install -r requirements.txt`.

To bundle everything into a Windows executable, run `pyinstaller --onefile EFogModSwap.py`,
which will generate a portable EXE at `.\dist\EFogModSwap.exe`.
