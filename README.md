# Blender MCP for Antigravity AI

![License](https://img.shields.io/badge/license-Custom_Non--Commercial-blue.svg)
![Version](https://img.shields.io/badge/version-2.0.0-green.svg)

## 📌 Description
**Blender MCP** is a bridge server and add-on that connects **Antigravity AI** directly to your Blender 3D environment. By using the Model Context Protocol (MCP), Antigravity AI gains full control and access to Blender via a local socket connection. 

With this project, Antigravity AI can natively:
* Analyze your current Blender Scene (objects, materials, camera positions).
* Create and manipulate 3D geometry dynamically.
* Take direct screenshots of the 3D Viewport to understand the visual state.
* Create and play detailed keyframe animations.
* Execute arbitrary Python scripts directly inside the Blender environment.

This empowers developers and creatives to use Antigravity as a virtual technical director and animator inside Blender!

---

## 🚀 Step-by-Step Setup Guide

To get everything running, you need to start the Node.js MCP Server and install the attached Add-on in Blender.

### Step 1: Open the Project & Install Dependencies
From your terminal or code editor (like VS Code), make sure you are inside the `blender-mcp` folder and install the required Node modules.

```bash
cd blender-mcp
npm install
```

### Step 2: Start the Node.js MCP Bridge
Once dependencies are installed, you need to start the bridge server. This is the server that Antigravity talks to.

```bash
npm start
```
*Tip: Leave this terminal window open in the background so the server keeps running.*

---

## 🎨 How to Make and Install the Blender Add-on

To allow Blender to communicate with the Node.js server, you must install the provided Python add-on into your Blender setup.

### 1. Package the Add-on
1. Open your file explorer and navigate to `blender-mcp/blender_extension/`
2. Right-click the folder named `blender_mcp_addon` and select **Compress to ZIP file** (or use your preferred zip tool).
3. Name it `blender_mcp_addon.zip`.

### 2. Install in Blender
1. Open **Blender**.
2. Go to `Edit` > `Preferences` > `Add-ons`.
3. Click the **Install...** button in the top right.
4. Locate the `blender_mcp_addon.zip` file you just created and select **Install Add-on**.
5. Once imported, search for "BlenderMCP" in the add-on search bar and **check the box** next to it to enable it. (It might show up under the *Antigravity MCP* category).

### 3. Connect the Bridge
1. Inside the Blender 3D Viewport, press the `N` key to open the right-side properties panel.
2. Click on the **BlenderMCP** tab.
3. You will see an **"Antigravity MCP"** panel. Ensure the port is set to `9876`.
4. Click the **Start MCP Server** button (with the Play icon). 
5. You should see a confirmation that the server has started successfully.

---

## 🛠️ Usage Workflow

Every time you want to use Antigravity with Blender, ensure you do the following two things:
1. Run `npm start` in your local `blender-mcp` terminal.
2. Open Blender, open the side panel (`N`), and click **Start MCP Server**.

Once both are running, Antigravity AI can use its tools to communicate seamlessly with your active Blender scene!
