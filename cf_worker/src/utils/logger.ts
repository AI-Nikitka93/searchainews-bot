type LogLevel = "debug" | "info" | "warn" | "error";

function emit(level: LogLevel, message: string, extra?: Record<string, unknown>): void {
  const payload = {
    ts: new Date().toISOString(),
    level,
    message,
    ...(extra ?? {})
  };

  const line = JSON.stringify(payload);
  if (level === "warn") {
    console.warn(line);
    return;
  }
  if (level === "error") {
    console.error(line);
    return;
  }
  console.log(line);
}

export const log = {
  debug: (message: string, extra?: Record<string, unknown>) => emit("debug", message, extra),
  info: (message: string, extra?: Record<string, unknown>) => emit("info", message, extra),
  warn: (message: string, extra?: Record<string, unknown>) => emit("warn", message, extra),
  error: (message: string, extra?: Record<string, unknown>) => emit("error", message, extra)
};
