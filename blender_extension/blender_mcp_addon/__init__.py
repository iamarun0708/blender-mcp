import bpy
import json
import threading
import socket
import time
import traceback
import io
import os
import math
from contextlib import redirect_stdout
from bpy.props import IntProperty, BoolProperty


class BlenderMCPServer:
    def __init__(self, host='localhost', port=9876):
        self.host = host
        self.port = port
        self.running = False
        self.socket = None
        self.server_thread = None

    def start(self):
        if self.running:
            print("BlenderMCP: Server already running")
            return
        self.running = True
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)
            self.server_thread = threading.Thread(target=self._server_loop, daemon=True)
            self.server_thread.start()
            print(f"BlenderMCP: Server started on {self.host}:{self.port}")
        except Exception as e:
            print(f"BlenderMCP: Failed to start server: {e}")
            self.running = False

    def stop(self):
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        print("BlenderMCP: Server stopped")

    def _server_loop(self):
        self.socket.settimeout(1.0)
        while self.running:
            try:
                client, addr = self.socket.accept()
                print(f"BlenderMCP: Client connected from {addr}")
                t = threading.Thread(target=self._handle_client, args=(client,), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"BlenderMCP: Accept error: {e}")
                    time.sleep(0.5)

    def _handle_client(self, client):
        buffer = b''
        client.settimeout(None)
        try:
            while self.running:
                data = client.recv(65536)
                if not data:
                    break
                buffer += data
                while buffer:
                    try:
                        command = json.loads(buffer.decode('utf-8'))
                        buffer = b''

                        def execute_wrapper(cmd=command, c=client):
                            try:
                                response = self.execute_command(cmd)
                                c.sendall(json.dumps(response).encode('utf-8'))
                            except Exception as ex:
                                try:
                                    c.sendall(json.dumps({
                                        "status": "error",
                                        "message": str(ex)
                                    }).encode('utf-8'))
                                except:
                                    pass
                            return None

                        bpy.app.timers.register(execute_wrapper, first_interval=0.0)
                        break
                    except json.JSONDecodeError:
                        break
        except Exception as e:
            print(f"BlenderMCP: Client error: {e}")
        finally:
            try:
                client.close()
            except:
                pass

    def execute_command(self, command):
        try:
            cmd_type = command.get("type")
            params = command.get("params", {})

            handlers = {
                "get_scene_info": self.get_scene_info,
                "get_object_info": self.get_object_info,
                "execute_code": self.execute_code,
                "get_viewport_screenshot": self.get_viewport_screenshot,
                "create_animation": self.create_animation,
                "add_keyframe": self.add_keyframe,
                "set_frame": self.set_frame,
                "play_animation": self.play_animation,
                "create_object": self.create_object,
                "delete_object": self.delete_object,
                "set_material": self.set_material,
                "render_frame": self.render_frame,
                "list_objects": self.list_objects,
                "clear_scene": self.clear_scene,
                "ping": self.ping,
            }

            handler = handlers.get(cmd_type)
            if handler:
                result = handler(**params)
                return {"status": "success", "result": result}
            else:
                return {"status": "error", "message": f"Unknown command: {cmd_type}"}
        except Exception as e:
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    # ── Utility ──────────────────────────────────────────────────────────

    def ping(self):
        return {"pong": True, "version": "2.0", "blender": bpy.app.version_string}

    def get_scene_info(self):
        scene = bpy.context.scene
        return {
            "name": scene.name,
            "frame_current": scene.frame_current,
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
            "fps": scene.render.fps,
            "object_count": len(scene.objects),
            "objects": [
                {
                    "name": o.name,
                    "type": o.type,
                    "location": list(o.location),
                    "rotation": list(o.rotation_euler),
                    "scale": list(o.scale),
                }
                for o in list(scene.objects)[:20]
            ],
        }

    def get_object_info(self, name):
        obj = bpy.data.objects.get(name)
        if not obj:
            raise ValueError(f"Object not found: {name}")
        info = {
            "name": obj.name,
            "type": obj.type,
            "location": list(obj.location),
            "rotation": list(obj.rotation_euler),
            "scale": list(obj.scale),
            "visible": obj.visible_get(),
            "animation_data": bool(obj.animation_data),
        }
        if obj.animation_data and obj.animation_data.action:
            action = obj.animation_data.action
            info["action"] = {
                "name": action.name,
                "frame_range": list(action.frame_range),
                "fcurves": len(action.fcurves),
            }
        return info

    def list_objects(self):
        return [{"name": o.name, "type": o.type} for o in bpy.context.scene.objects]

    def execute_code(self, code):
        namespace = {"bpy": bpy, "math": math}
        buf = io.StringIO()
        with redirect_stdout(buf):
            exec(code, namespace)
        return {"executed": True, "output": buf.getvalue()}

    def get_viewport_screenshot(self, filepath=None, max_size=800):
        if not filepath:
            filepath = os.path.join(os.path.expanduser("~"), "blender_viewport.png")
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                with bpy.context.temp_override(area=area):
                    bpy.ops.screen.screenshot_area(filepath=filepath)
                return {"filepath": filepath, "success": True}
        return {"error": "No 3D viewport found"}

    # ── Object Commands ──────────────────────────────────────────────────

    def create_object(self, type="CUBE", name=None, location=(0, 0, 0),
                      rotation=(0, 0, 0), scale=(1, 1, 1)):
        type_upper = type.upper()
        ops_map = {
            "CUBE": bpy.ops.mesh.primitive_cube_add,
            "SPHERE": bpy.ops.mesh.primitive_uv_sphere_add,
            "CYLINDER": bpy.ops.mesh.primitive_cylinder_add,
            "CONE": bpy.ops.mesh.primitive_cone_add,
            "PLANE": bpy.ops.mesh.primitive_plane_add,
            "TORUS": bpy.ops.mesh.primitive_torus_add,
            "MONKEY": bpy.ops.mesh.primitive_monkey_add,
            "EMPTY": bpy.ops.object.empty_add,
            "CAMERA": bpy.ops.object.camera_add,
            "LIGHT": bpy.ops.object.light_add,
        }
        op = ops_map.get(type_upper)
        if not op:
            raise ValueError(f"Unknown object type: {type}")
        op(location=tuple(location), rotation=tuple(rotation))
        obj = bpy.context.active_object
        if name:
            obj.name = name
        obj.scale = tuple(scale)
        return {"name": obj.name, "type": obj.type, "location": list(obj.location)}

    def delete_object(self, name):
        obj = bpy.data.objects.get(name)
        if not obj:
            raise ValueError(f"Object not found: {name}")
        bpy.data.objects.remove(obj, do_unlink=True)
        return {"deleted": name}

    def clear_scene(self, keep_camera=True, keep_lights=True):
        removed = []
        for obj in list(bpy.data.objects):
            if keep_camera and obj.type == 'CAMERA':
                continue
            if keep_lights and obj.type == 'LIGHT':
                continue
            removed.append(obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)
        return {"removed": removed}

    def set_material(self, object_name, color=(0.8, 0.2, 0.2, 1.0),
                     metallic=0.0, roughness=0.5, name=None):
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")
        mat_name = name or f"mat_{object_name}"
        mat = bpy.data.materials.get(mat_name) or bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = tuple(color)
            bsdf.inputs["Metallic"].default_value = metallic
            bsdf.inputs["Roughness"].default_value = roughness
        if obj.data and hasattr(obj.data, 'materials'):
            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)
        return {"material": mat.name, "applied_to": object_name}

    # ── Animation Commands ───────────────────────────────────────────────

    def set_frame(self, frame):
        bpy.context.scene.frame_set(int(frame))
        return {"frame": bpy.context.scene.frame_current}

    def add_keyframe(self, object_name, frame, location=None,
                     rotation=None, scale=None):
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        bpy.context.scene.frame_set(int(frame))

        if location is not None:
            obj.location = tuple(location)
            obj.keyframe_insert(data_path="location", frame=frame)
        if rotation is not None:
            obj.rotation_euler = tuple(rotation)
            obj.keyframe_insert(data_path="rotation_euler", frame=frame)
        if scale is not None:
            obj.scale = tuple(scale)
            obj.keyframe_insert(data_path="scale", frame=frame)

        return {
            "object": object_name,
            "frame": frame,
            "keyframed": {
                "location": location is not None,
                "rotation": rotation is not None,
                "scale": scale is not None,
            },
        }

    def create_animation(self, object_name, keyframes, frame_start=1,
                         frame_end=None, loop=False):
        """
        Create a full animation with multiple keyframes.
        keyframes: list of dicts with keys:
          - frame (int)
          - location (optional [x, y, z])
          - rotation (optional [x, y, z] in radians)
          - scale (optional [x, y, z])
        """
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"Object not found: {object_name}")

        scene = bpy.context.scene
        scene.frame_start = frame_start
        if frame_end:
            scene.frame_end = frame_end

        # Clear existing animation data
        if obj.animation_data:
            obj.animation_data_clear()

        total_keyframes = 0
        for kf in keyframes:
            frame = kf.get("frame")
            if frame is None:
                continue

            bpy.context.scene.frame_set(int(frame))

            if "location" in kf:
                obj.location = tuple(kf["location"])
                obj.keyframe_insert(data_path="location", frame=frame)
            if "rotation" in kf:
                obj.rotation_euler = tuple(kf["rotation"])
                obj.keyframe_insert(data_path="rotation_euler", frame=frame)
            if "scale" in kf:
                obj.scale = tuple(kf["scale"])
                obj.keyframe_insert(data_path="scale", frame=frame)

            total_keyframes += 1

        # Set interpolation to smooth (BEZIER) by default
        if obj.animation_data and obj.animation_data.action:
            for fc in obj.animation_data.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'BEZIER'

        if loop and obj.animation_data and obj.animation_data.action:
            for fc in obj.animation_data.action.fcurves:
                mod = fc.modifiers.new(type='CYCLES')
                mod.mode_before = 'REPEAT'
                mod.mode_after = 'REPEAT'

        bpy.context.scene.frame_set(frame_start)
        return {
            "object": object_name,
            "keyframes_set": total_keyframes,
            "frame_range": [scene.frame_start, scene.frame_end],
            "loop": loop,
        }

    def play_animation(self):
        bpy.ops.screen.animation_play()
        return {"playing": True}

    def render_frame(self, frame=None, filepath=None):
        scene = bpy.context.scene
        if frame is not None:
            scene.frame_set(int(frame))
        if filepath:
            scene.render.filepath = filepath
        bpy.ops.render.render(write_still=bool(filepath))
        return {
            "rendered": True,
            "frame": scene.frame_current,
            "filepath": scene.render.filepath,
        }


# ── Singleton server instance ────────────────────────────────────────────
_server = None


# ── Operators ────────────────────────────────────────────────────────────

class BLENDERMCP_OT_StartServer(bpy.types.Operator):
    bl_idname = "blendermcp.start_server"
    bl_label = "Start MCP Server"
    bl_description = "Start the BlenderMCP socket server for Antigravity"

    def execute(self, context):
        global _server
        if _server and _server.running:
            self.report({'WARNING'}, "Server already running")
            return {'CANCELLED'}
        port = context.scene.blendermcp_port
        _server = BlenderMCPServer(host='localhost', port=port)
        _server.start()
        context.scene.blendermcp_running = True
        self.report({'INFO'}, f"BlenderMCP started on port {port}")
        return {'FINISHED'}


class BLENDERMCP_OT_StopServer(bpy.types.Operator):
    bl_idname = "blendermcp.stop_server"
    bl_label = "Stop MCP Server"
    bl_description = "Stop the BlenderMCP socket server"

    def execute(self, context):
        global _server
        if _server:
            _server.stop()
            _server = None
        context.scene.blendermcp_running = False
        self.report({'INFO'}, "BlenderMCP server stopped")
        return {'FINISHED'}


# ── Panel ────────────────────────────────────────────────────────────────

class BLENDERMCP_PT_Panel(bpy.types.Panel):
    bl_label = "Antigravity MCP"
    bl_idname = "BLENDERMCP_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'BlenderMCP'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        running = scene.blendermcp_running

        box = layout.box()
        row = box.row()
        if running:
            row.label(text="Server Running", icon='CHECKMARK')
        else:
            row.label(text="Server Stopped", icon='X')

        layout.prop(scene, "blendermcp_port", text="Port")

        row = layout.row(align=True)
        if not running:
            row.operator("blendermcp.start_server", icon='PLAY')
        else:
            row.operator("blendermcp.stop_server", icon='PAUSE')

        layout.separator()
        box = layout.box()
        box.label(text="Connect Antigravity to:", icon='INFO')
        box.label(text=f"  localhost:{scene.blendermcp_port}")


# ── Registration ─────────────────────────────────────────────────────────

classes = [
    BLENDERMCP_OT_StartServer,
    BLENDERMCP_OT_StopServer,
    BLENDERMCP_PT_Panel,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.blendermcp_port = IntProperty(
        name="Port", default=9876, min=1024, max=65535
    )
    bpy.types.Scene.blendermcp_running = BoolProperty(
        name="Running", default=False
    )
    print("BlenderMCP (Antigravity) addon registered")


def unregister():
    global _server
    if _server:
        _server.stop()
        _server = None
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.blendermcp_port
    del bpy.types.Scene.blendermcp_running
