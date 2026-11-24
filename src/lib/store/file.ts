/**
 * The user store on local files: one JSON file per user under GODSEYE_DATA_DIR (default .data/).
 *
 * This is for running the app on one machine before the database exists. It is correct for a single
 * server process (updates for one user are queued), and it is not meant for a hosted, multi-instance
 * site: that is what the Postgres store is for.
 */
import { mkdir, readFile, readdir, rename, writeFile } from "node:fs/promises";
import path from "node:path";
import { newUser, validUserId, type UserRecord, type UserStore } from "./types.ts";

export class FileStore implements UserStore {
  private readonly dir: string;
  private readonly now: () => Date;
  private queues = new Map<string, Promise<unknown>>();

  constructor(dir = process.env.GODSEYE_DATA_DIR || path.join(process.cwd(), ".data"), now: () => Date = () => new Date()) {
    this.dir = path.join(dir, "users");
    this.now = now;
  }

  private file(id: string) {
    if (!validUserId(id)) throw new Error("That is not a valid user id.");
    return path.join(this.dir, `${id}.json`);
  }

  private async read(id: string): Promise<UserRecord> {
    try {
      const user = JSON.parse(await readFile(this.file(id), "utf8")) as UserRecord;
      // records written by an older version may lack newer fields
      return { ...newUser(id, this.now()), ...user, profile: { ...user.profile, summary: user.profile?.summary ?? "" } };
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return newUser(id, this.now());
      throw error;
    }
  }

  get(id: string) {
    return this.read(id);
  }

  update(id: string, change: (user: UserRecord) => void): Promise<UserRecord> {
    const file = this.file(id);
    const run = async () => {
      const user = await this.read(id);
      change(user);
      await mkdir(this.dir, { recursive: true });
      // write beside the file, then swap it in, so a crash never leaves half a record
      const tmp = `${file}.${process.pid}.tmp`;
      await writeFile(tmp, JSON.stringify(user));
      await rename(tmp, file);
      return user;
    };
    const next = (this.queues.get(id) ?? Promise.resolve()).then(run, run);
    this.queues.set(id, next.catch(() => undefined));
    return next;
  }

  async list() {
    try {
      return (await readdir(this.dir)).filter((f) => f.endsWith(".json")).map((f) => f.slice(0, -5)).filter(validUserId);
    } catch {
      return [];
    }
  }
}
