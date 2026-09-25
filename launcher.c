/* Small Windows launcher for the bundled Python desktop application. */
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <wchar.h>

typedef int (__cdecl *PythonMain)(int, wchar_t **);

int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, PWSTR command, int show) {
    wchar_t exe[32768], root[32768], library[32768], script[32768];
    DWORD size = GetModuleFileNameW(NULL, exe, 32768);
    if (!size || size >= 32700) return 1;
    wcscpy(root, exe);
    wchar_t *slash = wcsrchr(root, L'\\');
    if (!slash) return 1;
    *slash = 0;
    wcscpy(library, root);
    wcscat(library, L"\\_runtime\\python313.dll");
    wcscpy(script, root);
    wcscat(script, L"\\_runtime\\launch.py");
    HMODULE python = LoadLibraryExW(library, NULL,
        LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
    if (!python) {
        MessageBoxW(NULL, L"Please extract the entire ZIP first. Keep the _runtime folder beside HERA_CSV.exe.",
                    L"HERA CSV", MB_OK | MB_ICONERROR);
        return 1;
    }
    PythonMain run = (PythonMain)GetProcAddress(python, "Py_Main");
    if (!run) {
        MessageBoxW(NULL, L"The included Python runtime could not be loaded. Extract the ZIP again.",
                    L"HERA CSV", MB_OK | MB_ICONERROR);
        return 1;
    }
    wchar_t *arguments[] = {exe, L"-I", L"-B", script, NULL};
    return run(4, arguments);
}
