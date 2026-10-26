"""Read-only Windows display color state. Never changes OS display settings."""
import ctypes as C
import sys

U32, I32 = C.c_uint32, C.c_int32


class Luid(C.Structure):
    _fields_ = [('low', U32), ('high', I32)]


class Rational(C.Structure):
    _fields_ = [('numerator', U32), ('denominator', U32)]


class Source(C.Structure):
    _fields_ = [('adapter', Luid), ('id', U32), ('mode', U32), ('flags', U32)]


class Target(C.Structure):
    _fields_ = [('adapter', Luid), ('id', U32), ('mode', U32), ('technology', U32),
                ('rotation', U32), ('scaling', U32), ('refresh', Rational),
                ('scanline', U32), ('available', I32), ('flags', U32)]


class DisplayPath(C.Structure):
    _fields_ = [('source', Source), ('target', Target), ('flags', U32)]


class Header(C.Structure):
    _fields_ = [('type', U32), ('size', U32), ('adapter', Luid), ('id', U32)]


class ColorInfo(C.Structure):
    _fields_ = [('header', Header), ('flags', U32), ('encoding', U32), ('bits', U32)]


class ColorInfo2(C.Structure):
    _fields_ = ColorInfo._fields_ + [('active_mode', U32)]


class WhiteLevel(C.Structure):
    _fields_ = [('header', Header), ('level', U32)]


class SourceName(C.Structure):
    _fields_ = [('header', Header), ('name', C.c_wchar * 32)]


def screen_device_for_window(handle):
    """Read the monitor's GDI device name; QScreen may use its friendly name."""
    if sys.platform != 'win32': return ''
    class Rect(C.Structure):
        _fields_ = [(key, I32) for key in ('left', 'top', 'right', 'bottom')]
    class MonitorInfo(C.Structure):
        _fields_ = [('size', U32), ('monitor', Rect), ('work', Rect), ('flags', U32), ('device', C.c_wchar * 32)]
    try:
        api = C.WinDLL('user32', use_last_error=True)
        api.MonitorFromWindow.argtypes = [C.c_void_p, U32]
        api.MonitorFromWindow.restype = C.c_void_p
        api.GetMonitorInfoW.argtypes = [C.c_void_p, C.POINTER(MonitorInfo)]
        api.GetMonitorInfoW.restype = I32
        monitor = api.MonitorFromWindow(C.c_void_p(handle), 2)
        info = MonitorInfo();info.size = C.sizeof(info)
        return info.device if monitor and api.GetMonitorInfoW(monitor, C.byref(info)) else ''
    except (OSError, ValueError): return ''


def display_for_screen(status, screen_name):
    """Match QScreen's GDI name; never borrow another monitor's HDR state."""
    displays = status.get('displays', [])
    name = (screen_name or '').casefold()
    matched = [item for item in displays if item.get('screenName', '').casefold() == name]
    if matched:
        # Cloned SDR/HDR targets cannot safely share an HDR assertion.
        if len(matched) > 1 and not all(item.get('hdrEnabled') is True for item in matched):
            return {**matched[0], 'hdrEnabled': False}
        return matched[0]
    return displays[0] if len(displays) == 1 and not displays[0].get('screenName') else {}


def display_color_status():
    if sys.platform != 'win32':
        return {'available': False, 'reason': '仅支持 Windows', 'displays': []}
    try:
        api = C.WinDLL('user32', use_last_error=True)
        api.GetDisplayConfigBufferSizes.argtypes = [U32, C.POINTER(U32), C.POINTER(U32)]
        api.GetDisplayConfigBufferSizes.restype = I32
        api.QueryDisplayConfig.argtypes = [U32, C.POINTER(U32), C.POINTER(DisplayPath), C.POINTER(U32), C.c_void_p, C.c_void_p]
        api.QueryDisplayConfig.restype = I32
        api.DisplayConfigGetDeviceInfo.argtypes = [C.POINTER(Header)]
        api.DisplayConfigGetDeviceInfo.restype = I32
        for _ in range(3):
            path_count, mode_count = U32(), U32()
            code = api.GetDisplayConfigBufferSizes(2, C.byref(path_count), C.byref(mode_count))
            if code: raise OSError(code, '无法读取显示配置')
            if path_count.value > 64 or mode_count.value > 256:
                raise ValueError('显示配置条目超出限制')
            paths = (DisplayPath*path_count.value)()
            modes = C.create_string_buffer(64*mode_count.value)
            code = api.QueryDisplayConfig(2, C.byref(path_count), paths, C.byref(mode_count), modes, None)
            if code == 122: continue
            if code: raise OSError(code, '无法读取活动显示路径')
            displays = []
            for path in paths[:path_count.value]:
                source = SourceName(Header(1, C.sizeof(SourceName), path.source.adapter, path.source.id))
                source_ok = api.DisplayConfigGetDeviceInfo(C.byref(source.header)) == 0
                identity = {'screenName': source.name if source_ok else ''}
                info = ColorInfo2(Header(15, C.sizeof(ColorInfo2), path.target.adapter, path.target.id))
                result = api.DisplayConfigGetDeviceInfo(C.byref(info.header))
                if result == 0:
                    white = WhiteLevel(Header(11, C.sizeof(WhiteLevel), path.target.adapter, path.target.id))
                    white_ok = api.DisplayConfigGetDeviceInfo(C.byref(white.header)) == 0
                    displays.append({**identity, 'hdrSupported': bool(info.flags & 16),
                        'hdrEnabled': info.active_mode == 2,
                        'policyLimited': bool(info.flags & 8), 'bitsPerChannel': info.bits,
                        'activeColorMode': ('SDR', 'WCG', 'HDR')[info.active_mode] if info.active_mode < 3 else 'unknown',
                        'api': 'advanced-color-info-2',
                        'sdrWhiteNits': round(80*white.level/1000, 2) if white_ok else None})
                else:
                    legacy = ColorInfo(Header(9, C.sizeof(ColorInfo), path.target.adapter, path.target.id))
                    code = api.DisplayConfigGetDeviceInfo(C.byref(legacy.header))
                    displays.append({**identity, 'hdrSupported': None, 'hdrEnabled': None, 'bitsPerChannel': legacy.bits if not code else None,
                        'advancedColorSupported': bool(legacy.flags & 1) if not code else None,
                        'advancedColorEnabled': bool(legacy.flags & 2) if not code else None,
                        'api': 'legacy-advanced-color', 'note': '旧接口不能区分 HDR 与 WCG，不将其视为 HDR 证明'})
            return {'available': True, 'displays': displays, 'osSettingsChanged': False}
        raise OSError(122, '显示配置正在变化，请稍后重试')
    except (OSError, ValueError) as error:
        return {'available': False, 'reason': str(error), 'displays': [], 'osSettingsChanged': False}
