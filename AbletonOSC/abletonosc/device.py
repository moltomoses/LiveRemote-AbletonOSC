from typing import Tuple, Any
from .handler import AbletonOSCHandler

class DeviceHandler(AbletonOSCHandler):
    def __init__(self, manager):
        super().__init__(manager)
        self.class_identifier = "device"

    def init_api(self):
        def create_device_callback(func, *args, include_ids: bool = False,
                                   resolve_device: bool = True):
            def device_callback(params: Tuple[Any]):
                track_index, device_index = int(params[0]), int(params[1])
                # Stop-listener callbacks use the object saved when the
                # listener was created. Do not resolve the current indexed
                # device first: it may already have been deleted/replaced.
                device = (self.song.tracks[track_index].devices[device_index]
                          if resolve_device else None)
                if (include_ids):
                    rv = func(device, *args, params[0:])
                else:
                    rv = func(device, *args, params[2:])

                if rv is not None:
                    return (track_index, device_index, *rv)

            return device_callback

        methods = [
        ]
        properties_r = [
            "class_name",
            "class_display_name",
            "name",
            "type",
            "can_have_chains",
            "can_have_drum_pads"
        ]
        properties_rw = [
        ]

        # These identity/capability properties are readable but only `name`
        # is guaranteed observable in the Live Object Model.
        observable_properties = ["name"]

        for method in methods:
            self.osc_server.add_handler("/live/device/%s" % method,
                                        create_device_callback(self._call_method, method))

        for prop in properties_r + properties_rw:
            self.osc_server.add_handler("/live/device/get/%s" % prop,
                                        create_device_callback(self._get_property, prop))
        for prop in observable_properties:
            self.osc_server.add_handler("/live/device/start_listen/%s" % prop,
                                        create_device_callback(self._start_listen, prop, include_ids=True))

            def stop_property_listener(device, params: Tuple[Any] = (), property_name=prop):
                listener_key = (property_name, tuple(params))
                target = self.listener_objects.get(listener_key)
                if target is not None:
                    self._stop_listen(target, property_name, params)

            self.osc_server.add_handler("/live/device/stop_listen/%s" % prop,
                                        create_device_callback(stop_property_listener,
                                                               include_ids=True,
                                                               resolve_device=False))
        for prop in properties_rw:
            self.osc_server.add_handler("/live/device/set/%s" % prop,
                                        create_device_callback(self._set_property, prop))

        #--------------------------------------------------------------------------------
        # Device: Get/set parameter lists
        #--------------------------------------------------------------------------------
        def device_get_num_parameters(device, params: Tuple[Any] = ()):
            return len(device.parameters),

        def device_get_parameters_name(device, params: Tuple[Any] = ()):
            return tuple(parameter.name for parameter in device.parameters)

        def device_get_parameters_value(device, params: Tuple[Any] = ()):
            return tuple(parameter.value for parameter in device.parameters)

        def device_get_parameters_min(device, params: Tuple[Any] = ()):
            return tuple(parameter.min for parameter in device.parameters)

        def device_get_parameters_max(device, params: Tuple[Any] = ()):
            return tuple(parameter.max for parameter in device.parameters)

        def device_get_parameters_is_quantized(device, params: Tuple[Any] = ()):
            return tuple(parameter.is_quantized for parameter in device.parameters)

        def device_get_parameters_value_string(device, params: Tuple[Any] = ()):
            return tuple(parameter.str_for_value(parameter.value) for parameter in device.parameters)

        def device_get_parameters_original_name(device, params: Tuple[Any] = ()):
            return tuple(parameter.original_name for parameter in device.parameters)

        def device_get_parameters_is_enabled(device, params: Tuple[Any] = ()):
            return tuple(parameter.is_enabled for parameter in device.parameters)

        def device_set_parameters_value(device, params: Tuple[Any] = ()):
            for index, value in enumerate(params):
                device.parameters[index].value = value

        self.osc_server.add_handler("/live/device/get/num_parameters", create_device_callback(device_get_num_parameters))
        self.osc_server.add_handler("/live/device/get/parameters/name", create_device_callback(device_get_parameters_name))
        self.osc_server.add_handler("/live/device/get/parameters/value", create_device_callback(device_get_parameters_value))
        self.osc_server.add_handler("/live/device/get/parameters/min", create_device_callback(device_get_parameters_min))
        self.osc_server.add_handler("/live/device/get/parameters/max", create_device_callback(device_get_parameters_max))
        self.osc_server.add_handler("/live/device/get/parameters/is_quantized", create_device_callback(device_get_parameters_is_quantized))
        self.osc_server.add_handler("/live/device/get/parameters/value_string", create_device_callback(device_get_parameters_value_string))
        self.osc_server.add_handler("/live/device/get/parameters/original_name", create_device_callback(device_get_parameters_original_name))
        self.osc_server.add_handler("/live/device/get/parameters/is_enabled", create_device_callback(device_get_parameters_is_enabled))
        self.osc_server.add_handler("/live/device/set/parameters/value", create_device_callback(device_set_parameters_value))

        # Live's Configure button changes Device.parameters while the device
        # remains selected. A dedicated change event matters because replacing
        # or reordering controls can leave the count unchanged.
        def device_start_parameters_listener(device, params: Tuple[Any] = ()):
            track_index, device_index = int(params[0]), int(params[1])
            listener_key = ('parameters', (track_index, device_index))
            if listener_key in self.listener_functions:
                device_stop_parameters_listener(device, params)

            def parameters_changed_callback():
                try:
                    self.osc_server.send("/live/device/get/parameters_changed",
                                         (track_index, device_index, len(device.parameters)))
                except Exception as e:
                    self.logger.warning("Device parameters listener failed (ignored): %s" % e)

            device.add_parameters_listener(parameters_changed_callback)
            self.listener_functions[listener_key] = parameters_changed_callback
            self.listener_objects[listener_key] = device
            self.osc_server.send("/live/device/get/num_parameters",
                                 (track_index, device_index, len(device.parameters)))

        def device_stop_parameters_listener(device, params: Tuple[Any] = ()):
            track_index, device_index = int(params[0]), int(params[1])
            listener_key = ('parameters', (track_index, device_index))
            callback = self.listener_functions.pop(listener_key, None)
            target = self.listener_objects.pop(listener_key, None)
            if callback is not None and target is not None:
                try:
                    target.remove_parameters_listener(callback)
                except Exception as e:
                    self.logger.info("Exception whilst removing parameters listener (likely benign): %s" % e)

        self.osc_server.add_handler("/live/device/start_listen/parameters",
                                    create_device_callback(device_start_parameters_listener, include_ids=True))
        self.osc_server.add_handler("/live/device/stop_listen/parameters",
                                    create_device_callback(device_stop_parameters_listener,
                                                           include_ids=True,
                                                           resolve_device=False))

        #--------------------------------------------------------------------------------
        # Device: Get/set individual parameters
        #--------------------------------------------------------------------------------
        def device_get_parameter_value(device, params: Tuple[Any] = ()):
            # Cast to ints so that we can tolerate floats from interfaces such as TouchOSC
            # that send floats by default.
            # https://github.com/ideoforms/AbletonOSC/issues/33
            param_index = int(params[0])
            return param_index, device.parameters[param_index].value
        
        # Uses str_for_value method to return the UI-friendly version of a parameter value (ex: "2500 Hz")
        def device_get_parameter_value_string(device, params: Tuple[Any] = ()):
            param_index = int(params[0])
            return param_index, device.parameters[param_index].str_for_value(device.parameters[param_index].value)
        
        def device_get_parameter_value_listener(device, params: Tuple[Any] = ()):

            track_index, device_index, param_index = (int(params[0]), int(params[1]), int(params[2]))
            listener_key = ('value', (track_index, device_index, param_index))
            parameter = device.parameters[param_index]

            def property_changed_callback():
                try:
                    value = parameter.value
                    ids = (track_index, device_index, param_index)
                    self.logger.info("Property %s changed of %s %s: %s" % ('value', 'device parameter', str(ids), value))
                    self.osc_server.send("/live/device/get/parameter/value", (*ids, value,))

                    value_string = parameter.str_for_value(value)
                    self.logger.info("Property %s changed of %s %s: %s" % ('value_string', 'device parameter', str(ids), value_string))
                    self.osc_server.send("/live/device/get/parameter/value_string", (*ids, value_string,))
                except Exception as e:
                    self.logger.warning("Device parameter listener failed (ignored): %s" % e)

            if listener_key in self.listener_functions:
               device_get_parameter_remove_value_listener(device, params)

            self.logger.info("Adding listener for %s %s, property: %s" %
                             ('device parameter', str((track_index, device_index, param_index)), 'value'))
            parameter.add_value_listener(property_changed_callback)
            self.listener_functions[listener_key] = property_changed_callback
            self.listener_objects[listener_key] = parameter

            property_changed_callback()

        def device_get_parameter_remove_value_listener(device, params: Tuple[Any] = ()):
            track_index, device_index, param_index = (int(params[0]), int(params[1]), int(params[2]))
            listener_key = ('value', (track_index, device_index, param_index))
            listener_function = self.listener_functions.pop(listener_key, None)
            parameter = self.listener_objects.pop(listener_key, None)
            if listener_function is not None and parameter is not None:
                self.logger.info("Removing listener for %s %s, property %s" %
                                 (self.class_identifier, str((track_index, device_index, param_index)), 'value'))
                try:
                    parameter.remove_value_listener(listener_function)
                except Exception as e:
                    self.logger.info("Exception whilst removing parameter listener (likely benign): %s" % e)

        def device_set_parameter_value(device, params: Tuple[Any] = ()):
            param_index, param_value = params[:2]
            param_index = int(param_index)
            device.parameters[param_index].value = param_value

        def device_get_parameter_name(device, params: Tuple[Any] = ()):
            param_index = int(params[0])
            return param_index, device.parameters[param_index].name

        def device_get_parameter_value_items(device, params: Tuple[Any] = ()):
            param_index = int(params[0])
            try:
                return (param_index, *tuple(device.parameters[param_index].value_items))
            except (AttributeError, RuntimeError):
                return (param_index,)

        self.osc_server.add_handler("/live/device/get/parameter/value", create_device_callback(device_get_parameter_value))
        self.osc_server.add_handler("/live/device/get/parameter/value_string", create_device_callback(device_get_parameter_value_string))
        self.osc_server.add_handler("/live/device/set/parameter/value", create_device_callback(device_set_parameter_value))
        self.osc_server.add_handler("/live/device/get/parameter/name", create_device_callback(device_get_parameter_name))
        self.osc_server.add_handler("/live/device/get/parameter/value_items", create_device_callback(device_get_parameter_value_items))
        self.osc_server.add_handler("/live/device/start_listen/parameter/value", create_device_callback(device_get_parameter_value_listener, include_ids = True))
        self.osc_server.add_handler(
            "/live/device/stop_listen/parameter/value",
            create_device_callback(device_get_parameter_remove_value_listener,
                                   include_ids=True,
                                   resolve_device=False))

        # Live 12.3+ exposes host presets for PluginDevice. Many plug-ins expose
        # none; return an empty list / -1 so clients can capability-gate the UI.
        def device_get_presets(device, params: Tuple[Any] = ()):
            try:
                return tuple(device.presets)
            except (AttributeError, RuntimeError):
                return ()

        def device_get_selected_preset_index(device, params: Tuple[Any] = ()):
            try:
                return (int(device.selected_preset_index),)
            except (AttributeError, RuntimeError, TypeError):
                return (-1,)

        def device_set_selected_preset_index(device, params: Tuple[Any] = ()):
            try:
                device.selected_preset_index = int(params[0])
                return (int(device.selected_preset_index),)
            except (AttributeError, RuntimeError, TypeError, IndexError):
                return (-1,)

        self.osc_server.add_handler("/live/device/get/presets", create_device_callback(device_get_presets))
        self.osc_server.add_handler("/live/device/get/selected_preset_index",
                                    create_device_callback(device_get_selected_preset_index))
        self.osc_server.add_handler("/live/device/set/selected_preset_index",
                                    create_device_callback(device_set_selected_preset_index))
