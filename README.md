# kckfxgen - Calibre Plugin

This project is a fork of [kckfxgen](https://github.com/Exhen/kckfxgen). It adds several features to the original
project and integrates its functionality into a Calibre plugin.

## Requirements

- [Calibre](https://calibre-ebook.com/es/download)
- A Kindle device (jailbreaking is not required)
- A CBZ comic file (most importantly!)

## Installation

1. Download `generate_comic_kfx.zip`.
2. Open Calibre and navigate to **Preferences > Advanced > Plugins**.
3. Click **Load plugin from file**.
4. Select the downloaded `.zip` file.
5. Restart Calibre to complete the installation.

## Add to Toolbar

1. Go to **Preferences > Toolbars & menus**.
2. Select **The main toolbar** from the left-hand column.
3. Find **Generate Comic KFX** in the available actions.
4. Move it to the right-hand column and place it at your preferred position.

## How to Use

1. Select one or more comics in your Calibre library.
2. Click the **Generate Comic KFX** button.

![Toolbar icon](assets/toolbar_icon.png)

A configuration window will open, allowing you to select the reading direction:

- **LTR (Left to Right)**
- **RTL (Right to Left)**

![Configuration window](assets/gckfx_window.png)

## The Result

**Single-page layouts**

Regular pages are displayed full-screen, without any additional margins.

![Single page](assets/page_sample.png)

**Double-page layouts**

For double-page spreads, the Kindle automatically splits the image into two halves and displays them sequentially.

<table>
  <tr>
    <td><img src="assets/page_left.png" alt="Left page" /></td>
    <td><img src="assets/page_right.png" alt="Right page" /></td>
  </tr>
</table>

**Full-page landscape view**

Double-page spreads also include a popup that allows you to view the entire page in landscape orientation.

![Landscape view](assets/page_landscape.png)










