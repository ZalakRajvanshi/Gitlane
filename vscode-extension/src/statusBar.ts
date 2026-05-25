import * as vscode from "vscode";
import { GitMindDb } from "./db";
import { dbPath, getProjectRoot } from "./env";
import * as fs from "fs";

type GitAPI = {
  repositories: Array<{
    rootUri: vscode.Uri;
    state: {
      indexChanges: unknown[];
      workingTreeChanges: unknown[];
      onDidChange: vscode.Event<void>;
    };
  }>;
  onDidOpenRepository: vscode.Event<{ rootUri: vscode.Uri; state: { onDidChange: vscode.Event<void> } }>;
};

export class StatusBar {
  private item: vscode.StatusBarItem;
  private streak = 0;
  private dbReady = false;
  private disposables: vscode.Disposable[] = [];
  private pollTimer: NodeJS.Timeout | undefined;
  private dbWatcher: fs.FSWatcher | undefined;

  constructor() {
    this.item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    this.item.command = "gitmind.showMenu";
    this.item.tooltip = "Click for GitMind menu";
    this.item.show();
    this.render();
  }

  async attach(): Promise<void> {
    await this.refresh();
    this.pollTimer = setInterval(() => this.refresh().catch(() => {}), 5 * 60 * 1000);
    this.watchDb();
    await this.wireGit();
  }

  /** Watches data/gitmind.db for changes (Python CLI / 6 PM tick writes) so the streak updates instantly. */
  private watchDb(): void {
    const root = getProjectRoot();
    if (!root) return;
    const file = dbPath(root);
    if (!fs.existsSync(file)) return;
    try {
      this.dbWatcher = fs.watch(file, { persistent: false }, () => {
        this.refresh().catch(() => {});
      });
    } catch {
      // best-effort
    }
  }

  private async wireGit(): Promise<void> {
    const gitExt = vscode.extensions.getExtension<{ getAPI(v: number): GitAPI }>("vscode.git");
    if (!gitExt) return;
    const git = (await gitExt.activate()).getAPI(1);
    const wire = (repoState: { onDidChange: vscode.Event<void> }) =>
      this.disposables.push(repoState.onDidChange(() => this.render()));
    git.repositories.forEach(r => wire(r.state));
    this.disposables.push(git.onDidOpenRepository(r => wire(r.state)));
  }

  async refresh(): Promise<void> {
    const root = getProjectRoot();
    if (!root || !fs.existsSync(dbPath(root))) {
      this.dbReady = false;
      this.render();
      return;
    }
    try {
      const db = new GitMindDb(dbPath(root));
      const stats = await db.getStats();
      this.streak = stats.streak;
      this.dbReady = true;
    } catch {
      this.dbReady = false;
    }
    this.render();
  }

  private dirtyCount(): number {
    const gitExt = vscode.extensions.getExtension<{ getAPI(v: number): GitAPI }>("vscode.git");
    if (!gitExt?.isActive) return 0;
    const git = gitExt.exports.getAPI(1);
    return git.repositories.reduce(
      (n, r) => n + r.state.indexChanges.length + r.state.workingTreeChanges.length,
      0,
    );
  }

  private render(): void {
    if (!this.dbReady) {
      this.item.text = "$(gear) GitMind: set up";
      this.item.tooltip = "Click to pick the GitMind project folder";
      this.item.backgroundColor = undefined;
      return;
    }
    const dirty = this.dirtyCount();
    const streakPart = this.streak > 0 ? `🔥 ${this.streak}` : "⚡";
    if (dirty > 0) {
      this.item.text = `${streakPart} · ${dirty} to commit`;
      this.item.backgroundColor = new vscode.ThemeColor("statusBarItem.warningBackground");
    } else {
      this.item.text = `${streakPart} ✓`;
      this.item.backgroundColor = undefined;
    }
  }

  dispose(): void {
    if (this.pollTimer) clearInterval(this.pollTimer);
    this.dbWatcher?.close();
    this.disposables.forEach(d => d.dispose());
    this.item.dispose();
  }
}
