from functools import partial
from typing import Optional, Tuple, Any
from .handler import AbletonOSCHandler

class ViewHandler(AbletonOSCHandler):
    def __init__(self, manager):
        super().__init__(manager)
        self.class_identifier = "view"

    def init_api(self):
        #--------------------------------------------------------------------------------
        # Defensive getters (vendored fix for LiveRemote): selecting the
        # Master or a Return track raises ValueError from .index(), and an
        # exception inside a Live listener callback corrupts the control
        # surface (handlers go "Unknown" until Live restarts). Report -1
        # for "no regular track/scene selected" instead.
        #--------------------------------------------------------------------------------
        def get_selected_scene(params: Optional[Tuple] = ()):
            try:
                return (list(self.song.scenes).index(self.song.view.selected_scene),)
            except ValueError:
                return (-1,)

        def get_selected_track(params: Optional[Tuple] = ()):
            try:
                return (list(self.song.tracks).index(self.song.view.selected_track),)
            except ValueError:
                return (-1,)

        def get_selected_clip(params: Optional[Tuple] = ()):
            return (get_selected_track()[0], get_selected_scene()[0])
        
        def get_selected_device(params: Optional[Tuple] = ()):
            """Return the selected top-level device as ``(track, device)``.

            Track.View.selected_device can be None, can belong to a nested Rack
            chain, and is also reachable while a Return or Master track is
            selected. Those targets cannot be addressed by AbletonOSC's current
            track/device-index API, so report -1 instead of raising from a Live
            listener callback.
            """
            track_index = get_selected_track()[0]
            if track_index < 0:
                return (-1, -1)
            track = self.song.tracks[track_index]
            device = track.view.selected_device
            if device is None:
                return (track_index, -1)
            try:
                return (track_index, list(track.devices).index(device))
            except ValueError:
                return (track_index, -1)

        def set_selected_scene(params: Optional[Tuple] = ()):
            self.song.view.selected_scene = self.song.scenes[params[0]]

        def set_selected_track(params: Optional[Tuple] = ()):
            self.song.view.selected_track = self.song.tracks[params[0]]

        def set_selected_clip(params: Optional[Tuple] = ()):
            set_selected_track((params[0],))
            set_selected_scene((params[1],))

        def set_selected_device(params: Optional[Tuple] = ()):
            device = self.song.tracks[params[0]].devices[params[1]]
            self.song.view.select_device(device)
            return params[0], params[1]

        # Track.View owns selected_device. Following it requires a composite
        # listener that rebinds whenever Live changes the selected track. Both
        # callbacks use the normal listener tables so /live/api/reload clears
        # them safely.
        follow_params = ("selected_device_follow",)

        def stop_selected_device_listener(params: Optional[Tuple] = ()):
            device_key = ("selected_device", follow_params)
            if device_key in self.listener_functions:
                target = self.listener_objects[device_key]
                self._stop_listen(target, "selected_device", follow_params)

            track_key = ("selected_track", follow_params)
            if track_key in self.listener_functions:
                target = self.listener_objects[track_key]
                self._stop_listen(target, "selected_track", follow_params)

        def bind_selected_device_listener():
            device_key = ("selected_device", follow_params)
            if device_key in self.listener_functions:
                target = self.listener_objects[device_key]
                self._stop_listen(target, "selected_device", follow_params)

            track_index = get_selected_track()[0]
            if track_index < 0:
                self.osc_server.send("/live/view/get/selected_device_changed", (-1, -1))
                return

            target = self.song.tracks[track_index].view

            def selected_device_changed_callback():
                try:
                    self.osc_server.send("/live/view/get/selected_device_changed",
                                         get_selected_device())
                except Exception as e:
                    self.logger.warning("Selected-device listener failed (ignored): %s" % e)

            target.add_selected_device_listener(selected_device_changed_callback)
            self.listener_functions[device_key] = selected_device_changed_callback
            self.listener_objects[device_key] = target
            # Match the normal start-listen contract by immediately publishing
            # the current value, but on a distinct address so clients know this
            # is an identity event rather than an ordinary poll reply.
            selected_device_changed_callback()

        def start_selected_device_listener(params: Optional[Tuple] = ()):
            stop_selected_device_listener()

            def selected_track_changed_callback():
                try:
                    bind_selected_device_listener()
                except Exception as e:
                    self.logger.warning("Selected-device track listener failed (ignored): %s" % e)

            self.song.view.add_selected_track_listener(selected_track_changed_callback)
            track_key = ("selected_track", follow_params)
            self.listener_functions[track_key] = selected_track_changed_callback
            self.listener_objects[track_key] = self.song.view
            bind_selected_device_listener()

        self.osc_server.add_handler("/live/view/get/selected_scene", get_selected_scene)
        self.osc_server.add_handler("/live/view/get/selected_track", get_selected_track)
        self.osc_server.add_handler("/live/view/get/selected_clip", get_selected_clip)
        self.osc_server.add_handler("/live/view/get/selected_device", get_selected_device)
        self.osc_server.add_handler("/live/view/set/selected_scene", set_selected_scene)
        self.osc_server.add_handler("/live/view/set/selected_track", set_selected_track)
        self.osc_server.add_handler("/live/view/set/selected_clip", set_selected_clip)
        self.osc_server.add_handler("/live/view/set/selected_device", set_selected_device)
        
        self.osc_server.add_handler('/live/view/start_listen/selected_scene', partial(self._start_listen, self.song.view, "selected_scene", getter=get_selected_scene))
        self.osc_server.add_handler('/live/view/start_listen/selected_track', partial(self._start_listen, self.song.view, "selected_track", getter=get_selected_track))
        self.osc_server.add_handler('/live/view/stop_listen/selected_scene', partial(self._stop_listen, self.song.view, "selected_scene"))
        self.osc_server.add_handler('/live/view/stop_listen/selected_track', partial(self._stop_listen, self.song.view, "selected_track"))
        self.osc_server.add_handler('/live/view/start_listen/selected_device', start_selected_device_listener)
        self.osc_server.add_handler('/live/view/stop_listen/selected_device', stop_selected_device_listener)
