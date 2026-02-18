export async function loadBuiltInTools() {
  await import('./shell_exec.js');
  await import('./powershell_exec.js');
  await import('./process_manage.js');
  await import('./python_exec.js');
  await import('./file_read.js');
  await import('./file_write.js');
  await import('./file_search.js');
  await import('./web_search.js');
  await import('./sqlite_query.js');
  await import('./http_request.js');
  await import('./js_exec.js');
  await import('./wait.js');
  await import('./create_tool.js');
}

export async function loadCustomTools() {
  const { loadPersistedTools, getCustomToolsDir } = await import('./dynamic_tooling.js');
  const result = loadPersistedTools();
  return { ...result, dir: getCustomToolsDir() };
}
