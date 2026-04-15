#!/usr/bin/env node

/**
 * Blender MCP Bridge Server
 * ─────────────────────────
 * Connects Antigravity AI (via MCP / stdio) to a Blender instance
 * running the BlenderMCP addon socket server.
 *
 * Flow:  Antigravity ──stdio──▶ this bridge ──TCP──▶ Blender addon
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import net from "node:net";

// ── Config ───────────────────────────────────────────────────────────────────
const BLENDER_HOST = process.env.BLENDER_HOST || "127.0.0.1";
const BLENDER_PORT = parseInt(process.env.BLENDER_PORT || "9876", 10);
const TIMEOUT_MS   = 30_000;

// ── TCP helper — send JSON command to Blender and return response ──────────
function sendToBlender(command) {
  return new Promise((resolve, reject) => {
    const client = new net.Socket();
    let buffer = "";
    const timer = setTimeout(() => {
      client.destroy();
      reject(new Error("Blender command timed out after " + TIMEOUT_MS + "ms"));
    }, TIMEOUT_MS);

    client.connect(BLENDER_PORT, BLENDER_HOST, () => {
      client.write(JSON.stringify(command));
    });
    client.on("data", (data) => {
      buffer += data.toString();
      try {
        const parsed = JSON.parse(buffer);
        clearTimeout(timer);
        client.destroy();
        resolve(parsed);
      } catch {
        // incomplete JSON – keep reading
      }
    });
    client.on("error", (err) => {
      clearTimeout(timer);
      reject(new Error("Blender connection error: " + err.message +
        ". Make sure Blender is running with the MCP addon started on port " + BLENDER_PORT));
    });
    client.on("close", () => {
      clearTimeout(timer);
      if (buffer) {
        try { resolve(JSON.parse(buffer)); } catch { reject(new Error("Incomplete response from Blender")); }
      }
    });
  });
}

// Helper: call Blender and return content array for MCP
async function blenderCall(type, params = {}) {
  const res = await sendToBlender({ type, params });
  if (res.status === "error") throw new Error(res.message);
  return [{ type: "text", text: JSON.stringify(res.result, null, 2) }];
}

// ── MCP Server Setup ─────────────────────────────────────────────────────────
const server = new McpServer({
  name: "blender-mcp",
  version: "2.0.0",
});

// ── Tool: ping ───────────────────────────────────────────────────────────────
server.tool(
  "blender_ping",
  "Check connection to Blender. Returns Blender version info.",
  {},
  async () => ({ content: await blenderCall("ping") })
);

// ── Tool: get_scene_info ─────────────────────────────────────────────────────
server.tool(
  "blender_get_scene_info",
  "Get information about the current Blender scene including objects, frame range, FPS.",
  {},
  async () => ({ content: await blenderCall("get_scene_info") })
);

// ── Tool: list_objects ───────────────────────────────────────────────────────
server.tool(
  "blender_list_objects",
  "List all objects in the current Blender scene.",
  {},
  async () => ({ content: await blenderCall("list_objects") })
);

// ── Tool: get_object_info ────────────────────────────────────────────────────
server.tool(
  "blender_get_object_info",
  "Get detailed info about a specific object: location, rotation, scale, animation data.",
  { name: z.string().describe("Name of the object") },
  async ({ name }) => ({ content: await blenderCall("get_object_info", { name }) })
);

// ── Tool: create_object ──────────────────────────────────────────────────────
server.tool(
  "blender_create_object",
  "Create a new 3D object in Blender. Types: CUBE, SPHERE, CYLINDER, CONE, PLANE, TORUS, MONKEY, CAMERA, LIGHT, EMPTY.",
  {
    type:     z.string().default("CUBE").describe("Object type"),
    name:     z.string().optional().describe("Custom name"),
    location: z.array(z.number()).length(3).default([0, 0, 0]).describe("[x, y, z] position"),
    rotation: z.array(z.number()).length(3).default([0, 0, 0]).describe("[x, y, z] rotation in radians"),
    scale:    z.array(z.number()).length(3).default([1, 1, 1]).describe("[x, y, z] scale"),
  },
  async (params) => ({ content: await blenderCall("create_object", params) })
);

// ── Tool: delete_object ──────────────────────────────────────────────────────
server.tool(
  "blender_delete_object",
  "Delete an object from the scene by name.",
  { name: z.string().describe("Object to delete") },
  async ({ name }) => ({ content: await blenderCall("delete_object", { name }) })
);

// ── Tool: clear_scene ────────────────────────────────────────────────────────
server.tool(
  "blender_clear_scene",
  "Remove all objects from the scene. Optionally keep camera and lights.",
  {
    keep_camera: z.boolean().default(true).describe("Keep camera"),
    keep_lights: z.boolean().default(true).describe("Keep lights"),
  },
  async (params) => ({ content: await blenderCall("clear_scene", params) })
);

// ── Tool: set_material ───────────────────────────────────────────────────────
server.tool(
  "blender_set_material",
  "Set the material (color/metallic/roughness) of an object.",
  {
    object_name: z.string().describe("Target object name"),
    color:       z.array(z.number()).length(4).default([0.8, 0.2, 0.2, 1.0]).describe("[R, G, B, A] values 0-1"),
    metallic:    z.number().min(0).max(1).default(0).describe("Metallic value"),
    roughness:   z.number().min(0).max(1).default(0.5).describe("Roughness value"),
    name:        z.string().optional().describe("Material name"),
  },
  async (params) => ({ content: await blenderCall("set_material", params) })
);

// ── Tool: add_keyframe ───────────────────────────────────────────────────────
server.tool(
  "blender_add_keyframe",
  "Add a keyframe to an object at a specific frame. You can keyframe location, rotation, and/or scale.",
  {
    object_name: z.string().describe("Object to animate"),
    frame:       z.number().describe("Frame number"),
    location:    z.array(z.number()).length(3).optional().describe("[x, y, z] position"),
    rotation:    z.array(z.number()).length(3).optional().describe("[x, y, z] radians"),
    scale:       z.array(z.number()).length(3).optional().describe("[x, y, z] scale"),
  },
  async (params) => ({ content: await blenderCall("add_keyframe", params) })
);

// ── Tool: create_animation ───────────────────────────────────────────────────
server.tool(
  "blender_create_animation",
  `Create a full animation on an object with multiple keyframes at once.
Each keyframe has: frame (int), and optionally location, rotation, scale arrays.
Example keyframes: [{"frame":1,"location":[0,0,0]},{"frame":30,"location":[5,0,3]},{"frame":60,"location":[0,0,0]}]`,
  {
    object_name: z.string().describe("Object to animate"),
    keyframes:   z.array(z.object({
      frame:    z.number(),
      location: z.array(z.number()).length(3).optional(),
      rotation: z.array(z.number()).length(3).optional(),
      scale:    z.array(z.number()).length(3).optional(),
    })).describe("Array of keyframe objects"),
    frame_start: z.number().default(1).describe("Animation start frame"),
    frame_end:   z.number().optional().describe("Animation end frame"),
    loop:        z.boolean().default(false).describe("Loop the animation"),
  },
  async (params) => ({ content: await blenderCall("create_animation", params) })
);

// ── Tool: set_frame ──────────────────────────────────────────────────────────
server.tool(
  "blender_set_frame",
  "Set the current frame in the timeline.",
  { frame: z.number().describe("Frame number to jump to") },
  async ({ frame }) => ({ content: await blenderCall("set_frame", { frame }) })
);

// ── Tool: play_animation ─────────────────────────────────────────────────────
server.tool(
  "blender_play_animation",
  "Play/toggle the animation in the Blender viewport.",
  {},
  async () => ({ content: await blenderCall("play_animation") })
);

// ── Tool: render_frame ───────────────────────────────────────────────────────
server.tool(
  "blender_render_frame",
  "Render the current or specified frame.",
  {
    frame:    z.number().optional().describe("Frame to render"),
    filepath: z.string().optional().describe("Output file path"),
  },
  async (params) => ({ content: await blenderCall("render_frame", params) })
);

// ── Tool: execute_code ───────────────────────────────────────────────────────
server.tool(
  "blender_execute_code",
  "Execute arbitrary Python code inside Blender. Use for advanced operations not covered by other tools.",
  { code: z.string().describe("Python code to execute in Blender") },
  async ({ code }) => ({ content: await blenderCall("execute_code", { code }) })
);

// ── Tool: get_viewport_screenshot ────────────────────────────────────────────
server.tool(
  "blender_screenshot",
  "Take a screenshot of the current 3D viewport.",
  {
    filepath: z.string().optional().describe("File path to save screenshot"),
  },
  async (params) => ({ content: await blenderCall("get_viewport_screenshot", params) })
);

// ── Start ────────────────────────────────────────────────────────────────────
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Blender MCP Bridge running — waiting for Antigravity...");
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
