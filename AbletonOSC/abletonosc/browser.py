import time
from collections import deque

import Live
from typing import Tuple
from .handler import AbletonOSCHandler

CHUNK_SIZE = 12
MAX_ITEMS = 500

SEARCH_MAX_RESULTS = 80
SEARCH_MAX_NODES = 4000
SEARCH_MAX_DEPTH = 7
SEARCH_TIME_BUDGET = 1.5
# Joins folder names in search replies; item names can contain "/" so a
# printable separator would corrupt the path split on the client.
SEARCH_PATH_SEPARATOR = "\x1f"

class BrowserHandler(AbletonOSCHandler):
    """Exposes Live's library browser (the same API Push uses).

    Items are addressed by an integer index path rooted at the category list,
    e.g. (5, 0, 3) = Samples -> first folder -> fourth item. Children are
    delivered in chunks so replies stay under the UDP datagram size.
    """

    def __init__(self, manager):
        super().__init__(manager)
        self.class_identifier = "browser"

    def _browser(self):
        return Live.Application.get_application().browser

    def _categories(self):
        browser = self._browser()
        categories = [
            ("Sounds", browser.sounds),
            ("Drums", browser.drums),
            ("Instruments", browser.instruments),
            ("Audio Effects", browser.audio_effects),
            ("MIDI Effects", browser.midi_effects),
            ("Plug-Ins", browser.plugins),
            ("Samples", browser.samples),
            ("Packs", browser.packs),
            ("User Library", browser.user_library),
            ("Current Project", browser.current_project),
        ]
        try:
            for folder in browser.user_folders:
                categories.append((folder.name, folder))
        except Exception:
            pass
        return categories

    def _resolve(self, path):
        if not path:
            return None
        categories = self._categories()
        if path[0] < 0 or path[0] >= len(categories):
            return None
        item = categories[path[0]][1]
        for index in path[1:]:
            children = list(item.children)
            if index < 0 or index >= len(children):
                return None
            item = children[index]
        return item

    def init_api(self):
        def get_children(params: Tuple = ()):
            path = [int(p) for p in params]
            if not path:
                entries = [(name, 1, 0) for name, _ in self._categories()]
            else:
                item = self._resolve(path)
                if item is None:
                    return
                entries = []
                for child in list(item.children)[:MAX_ITEMS]:
                    is_loadable = bool(child.is_loadable)
                    navigable = bool(child.is_folder) or not is_loadable
                    entries.append((str(child.name), int(navigable), int(is_loadable)))

            total = len(entries)
            offset = 0
            while True:
                chunk = entries[offset:offset + CHUNK_SIZE]
                message = [len(path)] + path + [total, offset]
                for i, (name, navigable, loadable) in enumerate(chunk):
                    message += [offset + i, name, navigable, loadable]
                self.osc_server.send("/live/browser/children", tuple(message))
                offset += CHUNK_SIZE
                if offset >= total:
                    break

        def load_item(params: Tuple = ()):
            path = [int(p) for p in params]
            item = self._resolve(path)
            if item is not None and item.is_loadable:
                self._browser().load_item(item)
                return tuple(params) + ("ok",)
            return tuple(params) + ("error",)

        def preview_item(params: Tuple = ()):
            path = [int(p) for p in params]
            item = self._resolve(path)
            if item is None:
                self.logger.info("preview: path %s did not resolve" % (path,))
                return
            self.logger.info("preview: calling preview_item on '%s' (loadable=%s)"
                             % (item.name, getattr(item, "is_loadable", "?")))
            self._browser().preview_item(item)

        def stop_preview(params: Tuple = ()):
            self._browser().stop_preview()

        def search(params: Tuple = ()):
            """Case-insensitive name search across the whole library.

            Breadth-first walk from the category roots, bounded on every
            axis (results, nodes visited, depth, wall clock) — handlers run
            on Live's UI thread, so an unbounded walk of Packs/Samples
            would freeze Live. Replies stream in chunks:

              /live/browser/search_result
                (query, total, offset, truncated,
                 then per item: path_len, p0..pn, display_path,
                 navigable, loadable)

            display_path joins every folder name from the category root
            down to the item itself with SEARCH_PATH_SEPARATOR.
            """
            if not params:
                return
            query = str(params[0]).strip().lower()
            if not query:
                return
            deadline = time.time() + SEARCH_TIME_BUDGET
            results = []
            scanned = 0
            truncated = False
            queue = deque()
            for index, (name, category) in enumerate(self._categories()):
                queue.append((category, [index], [str(name)]))
            while queue:
                if (len(results) >= SEARCH_MAX_RESULTS
                        or scanned >= SEARCH_MAX_NODES
                        or time.time() > deadline):
                    truncated = True
                    break
                item, path, names = queue.popleft()
                scanned += 1
                is_loadable = bool(getattr(item, "is_loadable", False))
                navigable = bool(getattr(item, "is_folder", False)) or not is_loadable
                if query in names[-1].lower():
                    results.append((path, names, navigable, is_loadable))
                if navigable and len(path) < SEARCH_MAX_DEPTH and len(queue) < SEARCH_MAX_NODES:
                    try:
                        for ci, child in enumerate(list(item.children)[:MAX_ITEMS]):
                            queue.append((child, path + [ci], names + [str(child.name)]))
                    except Exception:
                        pass

            # Prefix matches first, then alphabetical — BFS order already
            # put shallow items ahead within each bucket, which stable
            # sort preserves.
            results.sort(key=lambda r: (0 if r[1][-1].lower().startswith(query) else 1,
                                        r[1][-1].lower()))

            total = len(results)
            offset = 0
            # Smaller than CHUNK_SIZE: each entry carries the full display
            # path, and the datagram should stay under the ~1.5 KB MTU.
            chunk_size = 5
            while True:
                chunk = results[offset:offset + chunk_size]
                message = [str(params[0]), total, offset, int(truncated)]
                for path, names, navigable, is_loadable in chunk:
                    message += [len(path)] + path
                    message += [SEARCH_PATH_SEPARATOR.join(names),
                                int(navigable), int(is_loadable)]
                self.osc_server.send("/live/browser/search_result", tuple(message))
                offset += chunk_size
                if offset >= total:
                    break

        self.osc_server.add_handler("/live/browser/get/children", get_children)
        self.osc_server.add_handler("/live/browser/load", load_item)
        self.osc_server.add_handler("/live/browser/preview", preview_item)
        self.osc_server.add_handler("/live/browser/stop_preview", stop_preview)
        self.osc_server.add_handler("/live/browser/search", search)
