#!/usr/bin/env python3

import os
from subprocess import Popen
import sys
import pprint
import json
import argparse
import shutil
from subprocess import call, check_output, Popen
from PIL import Image, ImageFont
import psutil
import time
import subprocess as s
import io
import dbus
import PIL.Image as I
from wayfire.ipc import *
from wayfire.extra.ipc_utils import WayfireUtils
from wayfire.extra.stipc import Stipc
addr = os.getenv('WAYFIRE_SOCKET')
sock = WayfireSocket(addr)
stipc = Stipc(sock)

class ViewDropDown:
    def __init__(self, term) -> None:
        pass

        self.TERMINAL_CMD = term
        self.TERMINAL_WIDTH = 1000
        self.TERMINAL_HEIGHT = 600
        self.VIEW_STICKY = True # show the terminal in all workspaces, set False to disable
        self.VIEW_ALWAYS_ON_TOP = True # always on top even if another view get the focus, Set False to disable

        addr = os.getenv('WAYFIRE_SOCKET')
        self.sock = WayfireSocket(addr)

    def find_view(self):
        hidden_view = shown_view = None
        for v in sock.list_views():
            if v['app-id'].lower() == self.TERMINAL_CMD:
                if v['minimized']:
                    hidden_view = v
                else:
                    shown_view = v
        return hidden_view, shown_view

    def configure_view(self, view, output):
        if self.TERMINAL_WIDTH == 0 or self.TERMINAL_HEIGHT == 0:
            return
        wa = output['workarea']
        geom = view['geometry']
        x = wa['x'] + wa['width'] // 2 - geom['width'] // 2
        y = wa['y'] + wa['height'] // 2 - geom['height'] // 2
        sock.configure_view(view["id"], x, y, self.TERMINAL_WIDTH, self.TERMINAL_HEIGHT)
        sock.set_view_sticky(view["id"], self.VIEW_STICKY)
        sock.set_view_always_on_top(view["id"], self.VIEW_ALWAYS_ON_TOP)

    def show_view(self, hidden_view):
        sock.set_view_minimized(hidden_view['id'], False)
        self.configure_view(hidden_view, sock.get_focused_output())

    def hide_view(self, shown_view):
        sock.set_view_minimized(shown_view['id'], True)


    def run(self):
        hidden_view, shown_view = self.find_view()
        if not shown_view and not hidden_view:
            Popen(self.TERMINAL_CMD, start_new_session=True)
            time.sleep(1)
            hidden_view, shown_view = self.find_view()
            if shown_view:
                self.show_view(shown_view)
            else:
                print("Failed to start new terminal!")
        elif shown_view:
            self.hide_view(shown_view)
        else:
            self.show_view(hidden_view)

class Wayctl:
    def __init__(self):
        self.ws_utils = WayfireUtils(sock)
        # Create an ArgumentParser object to handle command-line arguments
        self.parser = argparse.ArgumentParser(
            description="wayctl script utility for controlling parts of the wayfire compositor through the command line interface or a script."
        )

        # Add command-line arguments for various actions

        # --view option: Get information about views
        self.parser.add_argument(
            "--view",
            nargs="*",
            help="Retrieve information about views. Usage: --view focused (to get information about the focused view), --view list (to list all views).",
        )

        # --workspace option: Set the focused view to another workspace
        self.parser.add_argument(
            "--workspace",
            nargs="*",
            help="Set the focused view to another workspace. Usage: --workspace set view focused <x-coordinate> <y-coordinate> (to set the focused view to the specified workspace coordinates).",
        )

        self.parser.add_argument(
            "--move_cursor",
            nargs="*",
            help="move mouse cursor position with <x-coordinate> <y-coordinate>",
        )

        # --dpms option: Set DPMS (Display Power Management Signaling) on/off/toggle
        self.parser.add_argument(
            "--dpms",
            nargs="*",
            help="Set DPMS (Display Power Management Signaling) state. Usage: --dpms on/off/toggle <monitor-name> (to turn DPMS on, off, or toggle its state for the specified monitor).",
        )

        # --output option: Get output (monitor) info
        self.parser.add_argument(
            "--output",
            nargs="*",
            help="Retrieve information about outputs (monitors). Usage: --output view list (to view a list of all outputs), --output focused (to get information about the focused output).",
        )

        # --screenshot option: Capture screenshots with various options
        self.parser.add_argument(
            "--screenshot",
            nargs="*",
            help="Capture screenshots with various options. Usage: --screenshot focused view (to capture a screenshot of the focused view), --screenshot slurp (to select a region to screenshot), --screenshot output all (to capture screenshots of all outputs).",
        )

        self.parser.add_argument(
            "--colorpicker",
            nargs="*",
            help="Color picker using slurp and grim",
        )

        # --session option: Print session-related information
        self.parser.add_argument(
            "--session",
            nargs="*",
            help="Print session-related information. Usage: --session save (to save views session), --session start (to start a Wayfire session).",
        )

        # --resize option: Resize views
        self.parser.add_argument(
            "--resize",
            nargs="*",
            help="Resize views. Usage: --resize views left/right/up/down (to resize views in the specified direction).",
        )

        # --switch option: Switch views side
        self.parser.add_argument(
            "--switch",
            nargs="*",
            help="Switch views side. Usage: --switch views (to switch views side).",
        )

        # --plugin option: manager plugins
        self.parser.add_argument(
            "--plugin",
            nargs="*",
            help="add, reload and load plugins",
        )

        self.parser.add_argument(
            "--drop",
            nargs="*",
            help="start a view in guake mode",
        )

        # Parse the command-line arguments
        self.args = self.parser.parse_args()

        self.args = self.parser.parse_args()

        self.sock = sock


    def xdg_open(self, path):
        call("xdg-open {0}".format(path).split())
    
    def screenshot_all_outputs(self):
        bus = dbus.SessionBus()
        desktop = bus.get_object(
            "org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop"
        )
        desktop.Screenshot(
            "Screenshot",
            {"handle_token": "my_token"},
            dbus_interface="org.freedesktop.portal.Screenshot",
        )
        # lets wait save the file before try opening it
        time.sleep(1)
        self.xdg_open("/tmp/out.png")

    def screenshot_focused_monitor(self):
        output = sock.get_focused_output()
        name = output["name"]
        output_file = "/tmp/output-{0}.png".format(name)
        call(["grim", "-o", name, output_file])
        self.xdg_open(output_file)

    def screenshot(self, id, filename):
        capture = get_msg_template("view-shot/capture")
        if capture is None:
            return
        capture["data"]["view-id"] = id
        capture["data"]["file"] = filename
        sock.send_json(capture)

    def view_focused(self):
        view = self.sock.get_focused_view()
        print("[{0}: {1}]".format(view["app-id"], view["title"]))
        view_str = json.dumps(view, indent=4)
        print(view_str)
        print("\n\n")

    def move_cursor(self, x, y):
        self.sock.move_cursor(x, y)

    def create_new_session_file(self, file_path):
        try:
            # Remove the old file if it exists
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Old session '{file_path}' removed.")

            # Create a new session file
            with open(file_path, "w") as file:
                file.write("")  # You can write initial content here if needed

            print(f"New session file '{file_path}' created successfully.")
            return file_path

        except Exception as e:
            print(f"Error creating session file: {e}")
            return None

    def add_cmdline(self, view, process):
        ws_views = self.ws_utils.get_workspaces_with_views()
        for view in self.sock.list_views():
            if process.pid == view["pid"]:
                view["cmdline"] = process.cmdline()
                for d in ws_views:
                    if d["view-id"] == view["id"]:
                        view["workspace"] = {"x": d["x"], "y": d["y"]}
                return view

    def save_views_session(self):
        list_views = self.sock.list_views()
        home = os.path.expanduser("~")
        wayfire = ".config/wayfire-session.json"
        save_path = os.path.join(home, wayfire)
        self.create_new_session_file(save_path)
        for view in list_views:
            view = self.add_cmdline(view, psutil.Process(view["pid"]))
            with open(save_path, "a") as f:
                json.dump(view, f, indent=4)
                f.write("\n--------view--------\n")

    def load_wayfire_session(self):
        home = os.path.expanduser("~")
        wayfire = ".config/wayfire-session.json"
        load_path = os.path.join(home, wayfire)
        with open(load_path, "r") as file:
            data = file.read()

        # Split the data using the separator '---SEPARATOR---'
        json_list = data.split("\n--------view--------\n")

        # Remove any empty strings
        json_list = [item for item in json_list if item]

        # Load each JSON object as a dictionary
        result = []
        for json_str in json_list:
            result.append(json.loads(json_str))

        return result

    def start_app(self, cmdline):
        return stipc.run_cmd(" ".join(cmdline))["pid"]

    def start_wayfire_session(self):
        views = self.load_wayfire_session()
        for view in views:
            if "workspace" not in view:
                continue
            workspace = view["workspace"]
            self.sock.set_workspace(workspace)
            cmdline = view["cmdline"]
            pid = self.start_app(cmdline)
            time.sleep(1)

            # FIXME need a limit for that in case there is no pid at all
            while 1:
                if pid:
                    break
            view_id = None
            for v in self.sock.list_views():
                if v["pid"] == pid:
                    view_id = v["id"]
            if not view_id:
                continue

            self.ws_utils.maximize(view_id)
            self.sock.set_workspace(workspace, view_id)
            self.ws_utils.maximize(view_id)

    def screenshot_geometry(self):
        output = self.sock.get_focused_output()
        focused_view = self.sock.get_focused_view()
        ox = output["geometry"]["x"]
        oy = output["workarea"]["y"]
        vwidth = focused_view["geometry"]["width"]
        vheight = focused_view["geometry"]["height"]
        view_geometry = "{0},{1} {2}x{3}".format(ox, oy, vwidth, vheight)
        return view_geometry, focused_view

    def screenshot_view_focused(self):
        focused = self.sock.get_focused_view()
        view_id = focused["id"]
        app_id = focused["app-id"]
        filename = f"/tmp/{app_id}-{view_id}.png"

        if os.path.exists(filename):
            os.remove(filename)

        self.screenshot_view_id(view_id, filename)
        stipc.run_cmd(f"xdg-open {filename}")

    def screenshot_focused_output(self):
        self.screenshot_focused_monitor()

    def run_slurp(self):
        return check_output(["slurp"]).decode().strip()

    def screenshot_slurp(self):
        slurp = self.run_slurp()
        focused = self.sock.get_focused_view()
        view_id = focused["id"]
        app_id = focused["app-id"]
        filename = f"/tmp/{app_id}-{view_id}.png"
        if os.path.exists(filename):
            os.remove(filename)
        cmd = ["grim", "-g", f"{slurp}", filename]
        # must use call because Popen will not hang while creating the file thus xdg-open may fail
        call(cmd)
        Popen(["xdg-open", filename])

    def screenshot_slurp_focused_view(self):
        self.screenshot_view_focused()
        time.sleep(1)
        slurp = self.run_slurp()
        focused = self.sock.get_focused_view()
        view_id = focused["id"]
        app_id = focused["app-id"]
        filename = f"/tmp/{app_id}-{view_id}.png"
        if os.path.exists(filename):
            os.remove(filename)
        cmd = ["grim", "-g", f"{slurp}", filename]
        call(cmd)
        Popen(["xdg-open", filename])

    def generate_screenshot_info(self, view_id, filename):
        font_size = 22
        font_filepath = "SourceCodePro-ExtraLight.otf"
        color = (80, 80, 80)
        view = self.sock.get_view(view_id)
        text = f"ID: {view['id']}, PID: {view['pid']}, Title: {view['title']}"
        font = ImageFont.truetype(font_filepath, size=font_size)
        mask_image = font.getmask(text, "L")
        size = mask_image.size[0] + 20, mask_image.size[1] + 20
        img = Image.new("RGBA", size)
        img.im.paste(color, (20, 20) + size, mask_image)
        img.save(filename)

    def capture_screen_pixel(self):
        p = s.check_output(["slurp"]).decode().strip()
        screenshot_data = s.check_output(["grim", "-g", p, "-t", "ppm", "-"])
        screenshot = I.open(io.BytesIO(screenshot_data))
        screenshot = screenshot.convert("RGB")
        pixel = screenshot.getpixel((screenshot.size[0] // 2, screenshot.size[1] // 2))
        color_code = "#{0:02X}{1:02X}{2:02X}".format(*pixel)
        Popen(["wl-copy", color_code])
        return color_code

    def screenshot_view_id(self, view_id, filename):
        self.screenshot(view_id, filename)

    def create_directory(self, directory):
        if os.path.exists(directory):
            shutil.rmtree(directory)
        os.makedirs(directory)

    def screenshot_view_list(self):
        self.create_directory("/tmp/screenshots")
        for view in self.sock.list_views():
            view_id = view["id"]
            filename = str(view_id) + ".png"
            filename = os.path.join("/tmp/screenshots", filename)
            self.screenshot(view_id, filename)
        Popen("xdg-open /tmp/screenshots".split())

    def dpms(self):
        if "off_all" in self.args.dpms:
            self.ws_utils.dpms("off")
        if "on_all" in self.args.dpms:
            self.ws_utils.dpms("on")
        if "on" in self.args.dpms:
            monitor_name = self.args.dpms[-1].strip()
            self.ws_utils.dpms("on", monitor_name)
        if "off" in self.args.dpms:
            if "timeout" in self.args.dpms:
                monitor_name = self.args.dpms[1].strip()
                timeout = int(self.args.dpms[3].strip())
                time.sleep(int(timeout))
                self.ws_utils.dpms("off", monitor_name)
            else:
                self.ws_utils.dpms("off")
        if "toggle" in self.args.dpms:
            monitor_name = self.args.dpms[-1].strip()
            focused_output = self.sock.get_focused_output()
            monitor_name = focused_output["name"]
            self.ws_utils.dpms("toggle", monitor_name)

    def view_list(self):
        views = self.sock.list_views()
        focused_view = self.sock.get_focused_view()
        focused_view_id = focused_view["id"]
        has_title = None
        if "has_title" in self.args.view:
            has_title = self.args.view.split("has_title ")[-1].strip()
        for view in views:
            # we do not need info about focused view
            # in case you need, just use the right wayctl call
            if view["id"] == focused_view_id:
                continue

            title = view["title"].lower()
            if has_title is not None:
                if has_title not in title:
                    continue
            print("[{0}: {1}]".format(view["app-id"], view["title"]))
            view = json.dumps(view, indent=4)
            print(view)
            print("\n\n")

    def list_plugins(self):
        plugins = self.list_plugins()
        for plugin in plugins:
            print(plugin)
            print(plugins[plugin])
            print("\n")

        print("Enabled Plugins ")
        print(self.list_enabled_plugins())

    def _reload_plugin(self, plugin_name):
        self.reload_plugin(plugin_name)

    def enable_plugin(self, plugin_name):
        self.enable_plugin(plugin_name)

    def disable_plugin(self, plugin_name):
        self.disable_plugin(plugin_name)


# the cyclomatic complexity became to high, need a better way to deal with
if __name__ == "__main__":
    wayctl = Wayctl()

    if wayctl.args.view is not None:
        if "focused" in wayctl.args.view[0]:
            wayctl.view_focused()
            sys.exit()

        if "list" in wayctl.args.view[0]:
            wayctl.view_list()
            sys.exit()

    if wayctl.args.dpms is not None:
        wayctl.dpms()

    if wayctl.args.colorpicker is not None:
        color_code = wayctl.capture_screen_pixel()
        print(color_code)

    if wayctl.args.screenshot is not None:
        if "focused" in wayctl.args.screenshot[0]:
            if "view" in wayctl.args.screenshot[1]:
                wayctl.screenshot_view_focused()

        if "slurp" in wayctl.args.screenshot[0]:
            if len(wayctl.args.screenshot) == 1:
                wayctl.screenshot_slurp()
            if "focused" in wayctl.args.screenshot[1]:
                if "view" in wayctl.args.screenshot[2]:
                    # this method is for gaming, in case you want slurp a game
                    # will take screenshot of the whole game view, open the screenshot
                    # and start slurp, after you select the area, it will give the final screenshot
                    # you can't slurp while gaming right, because the game has the mouse focus
                    wayctl.screenshot_slurp_focused_view()

        if "focused" in wayctl.args.screenshot[0]:
            if "output" in wayctl.args.screenshot[1]:
                wayctl.screenshot_focused_output()

        if "output" in wayctl.args.screenshot[0]:
            if "all" in wayctl.args.screenshot[1]:
                wayctl.screenshot_all_outputs()

        if "view" in wayctl.args.screenshot[0]:
            if "all" in wayctl.args.screenshot[1]:
                wayctl.screenshot_view_list()

    if wayctl.args.workspace is not None:
        if "set" in wayctl.args.workspace[0]:
            if "view" in wayctl.args.workspace[1]:
                if "focused" in wayctl.args.workspace[2]:
                    wx = int(wayctl.args.workspace[-1])
                    wy = int(wayctl.args.workspace[-2])
                    ws = {"x": wx, "y": wy}
                    focused_view_id = wayctl.sock.get_focused_view_id()
                    wayctl.sock.set_workspace(ws, focused_view_id)

    if wayctl.args.session is not None:
        if "save" in wayctl.args.session[0]:
            wayctl.save_views_session()

        if "start" in wayctl.args.session[0]:
            wayctl.start_wayfire_session()

    if wayctl.args.switch is not None:
        if "views" in wayctl.args.switch[0]:
            wayctl.switch_views_side()

    if wayctl.args.move_cursor is not None:
        x = wayctl.args.move_cursor[0]
        y = wayctl.args.move_cursor[1]
        wayctl.move_cursor(int(x), int(y))

    if wayctl.args.plugin is not None:
        if "reload" in wayctl.args.plugin:
            if wayctl.args.plugin[1] != "all":
                wayctl._reload_plugin(wayctl.args.plugin[1])
        if "enable" in wayctl.args.plugin:
            wayctl.enable_plugin(wayctl.args.plugin[1])
        if "disable" in wayctl.args.plugin:
            wayctl.disable_plugin(wayctl.args.plugin[1])
        if "list" in wayctl.args.plugin:
            wayctl.list_plugins()

    if wayctl.args.drop is not None:
        cmd = wayctl.args.drop[0]
        drop = ViewDropDown(cmd)
        drop.run()

    if wayctl.args.output is not None:
        if "list" in wayctl.args.output[0]:
            if "views" in wayctl.args.output[1]:
                output = utils.focused_output_views()
                pprint.pprint(output)

        if "focused" in wayctl.args.output[0]:
            output = wayctl.sock.get_focused_output()
            output = json.dumps(output, indent=4)
            print(output)
