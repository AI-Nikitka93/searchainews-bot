import type { Env, Role, Lang } from "../types";

export async function getUserRole(env: Env, userId: number): Promise<Role | null> {
  const query = env.DB.prepare("SELECT role FROM users WHERE user_id = ?");
  const result = await query.bind(userId).first<{ role?: Role }>();
  return result?.role ?? null;
}

export async function getUserLanguage(env: Env, userId: number): Promise<Lang | null> {
  const query = env.DB.prepare("SELECT language FROM users WHERE user_id = ?");
  const result = await query.bind(userId).first<{ language?: Lang }>();
  return result?.language ?? null;
}

export async function getUserProfile(
  env: Env,
  userId: number
): Promise<{ role: Role | null; language: Lang | null }> {
  const query = env.DB.prepare("SELECT role, language FROM users WHERE user_id = ?");
  const result = await query.bind(userId).first<{ role?: Role; language?: Lang }>();
  return {
    role: result?.role ?? null,
    language: result?.language ?? null
  };
}

export async function upsertUserRole(
  env: Env,
  userId: number,
  username: string | null,
  role: Role
): Promise<void> {
  const query = env.DB.prepare(
    "INSERT INTO users (user_id, username, role, updated_at) VALUES (?, ?, ?, datetime('now')) " +
      "ON CONFLICT(user_id) DO UPDATE SET username = excluded.username, role = excluded.role, updated_at = datetime('now')"
  );
  await query.bind(userId, username, role).run();
}

export async function upsertUserLanguage(
  env: Env,
  userId: number,
  username: string | null,
  language: Lang
): Promise<void> {
  const query = env.DB.prepare(
    "INSERT INTO users (user_id, username, language, updated_at) VALUES (?, ?, ?, datetime('now')) " +
      "ON CONFLICT(user_id) DO UPDATE SET username = excluded.username, language = excluded.language, updated_at = datetime('now')"
  );
  await query.bind(userId, username, language).run();
}

export async function getSubscribedUsers(
  env: Env
): Promise<Array<{ user_id: number; role: Role | null; language: Lang | null }>> {
  const query = env.DB.prepare(
    "SELECT user_id, role, language FROM users WHERE is_subscribed = 1"
  );
  const result = await query.all<{ user_id: number; role: Role | null; language: Lang | null }>();
  return result.results ?? [];
}
