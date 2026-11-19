import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import * as Dialog from "@radix-ui/react-dialog";
import {
  Network,
  Search,
  Files,
  BarChart3,
  Upload,
  ShieldCheck,
  Download,
  Trash2,
  X,
  RefreshCw,
} from "lucide-react";
import "./style.css";
type User = { user: string; tenant: string; role: string; groups: string[] };
type Doc = {
  id: string;
  filename: string;
  source: string;
  owner: string;
  groups: string[];
  version: number;
  status: string;
  error: string | null;
  updated_at: string;
};
type Citation = {
  chunk_id: string;
  document_id: string;
  source: string;
  version: number;
  text: string;
  score?: number;
};
export function App() {
  const [token, setToken] = useState(
      sessionStorage.getItem("contextmesh-token") || "",
    ),
    [credential, setCredential] = useState("");
  const [me, setMe] = useState<User | null>(null),
    [docs, setDocs] = useState<Doc[]>([]),
    [tab, setTab] = useState("search");
  const [query, setQuery] = useState(""),
    [results, setResults] = useState<Citation[]>([]),
    [answer, setAnswer] = useState<{
      answer: string;
      citations: Citation[];
      uncertain: boolean;
    } | null>(null);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [searched, setSearched] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false),
    [file, setFile] = useState<File | null>(null),
    [groups, setGroups] = useState("hr"),
    [source, setSource] = useState("");
  const [selected, setSelected] = useState<Doc | null>(null),
    [citation, setCitation] = useState<Citation | null>(null),
    [permissionGroups, setPermissionGroups] = useState("");
  const [filter, setFilter] = useState(""),
    [reports, setReports] = useState<
      { id: number; report: Record<string, unknown>; created_at: string }[]
    >([]);
  async function api(path: string, method = "GET", body?: unknown) {
    const form = body instanceof FormData;
    const response = await fetch("/api" + path, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(!form ? { "Content-Type": "application/json" } : {}),
      },
      body: body === undefined ? undefined : form ? body : JSON.stringify(body),
    });
    if (response.status === 204) return null;
    const data = await response.json();
    if (!response.ok)
      throw new Error(
        typeof data.detail === "string" ? data.detail : "Invalid request",
      );
    return data;
  }
  async function load() {
    const user = await api("/me");
    setMe(user);
    setDocs(await api("/documents"));
    if (user.role === "admin") setReports(await api("/evaluations"));
  }
  async function action(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    if (token) void action(load);
  }, [token]);
  async function download(doc: Doc) {
    const response = await fetch(`/api/documents/${doc.id}/download`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) throw new Error("Download denied or unavailable");
    const url = URL.createObjectURL(await response.blob());
    const a = document.createElement("a");
    a.href = url;
    a.download = doc.filename;
    a.click();
    URL.revokeObjectURL(url);
  }
  const citationButton = (c: Citation) => (
    <button
      className="citation-button"
      key={c.chunk_id}
      onClick={() =>
        void action(async () => setCitation(await api("/chunks/" + c.chunk_id)))
      }
    >
      <Files size={15} />
      {c.source} · v{c.version}
    </button>
  );
  if (!me)
    return (
      <main className="login">
        <div className="brand">
          <Network />
          ContextMesh
        </div>
        <h1>
          Your knowledge.
          <br />
          The right boundaries.
        </h1>
        <p>Search a permission-aware synthetic enterprise workspace.</p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            sessionStorage.setItem("contextmesh-token", credential);
            setToken(credential);
          }}
        >
          <label htmlFor="credential">Development bearer credential</label>
          <input
            id="credential"
            type="password"
            required
            value={credential}
            onChange={(e) => setCredential(e.target.value)}
          />
          <button>Open workspace</button>
        </form>
        <p className="muted">
          Use a configured tenant identity such as local-acme-hr. Demo
          authentication is not production SSO.
        </p>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
      </main>
    );
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <Network />
          ContextMesh
        </div>
        <div className="workspace">
          <span className="workspace-icon">{me.tenant[0].toUpperCase()}</span>
          <div>
            {me.tenant}
            <small>Knowledge workspace</small>
          </div>
        </div>
        <p className="nav-label">KNOWLEDGE</p>
        <nav>
          {[
            { id: "search", name: "Search & ask", Icon: Search },
            { id: "documents", name: "Document library", Icon: Files },
            ...(me.role === "admin"
              ? [{ id: "evaluation", name: "Evaluations", Icon: BarChart3 }]
              : []),
          ].map(({ id, name, Icon }) => (
            <button
              key={id}
              className={tab === id ? "active" : ""}
              onClick={() => setTab(id)}
            >
              <Icon size={18} />
              {name}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <ShieldCheck />
          <p>
            Permission-aware retrieval
            <small>
              Tenant and group filters apply before answer generation.
            </small>
          </p>
        </div>
        <div className="identity">
          <strong>{me.user}</strong>
          <small>{me.groups.join(", ")}</small>
          <button
            onClick={() => {
              sessionStorage.removeItem("contextmesh-token");
              setToken("");
              setMe(null);
              setResults([]);
              setAnswer(null);
              setDocs([]);
              setSelected(null);
              setCitation(null);
            }}
          >
            Sign out
          </button>
        </div>
      </aside>
      <div className="main">
        <header>
          <div>Workspace / {me.tenant} / Knowledge</div>
          <span className="demo-badge">SYNTHETIC DATA</span>
        </header>
        <main>
          <div className="page-title">
            <div>
              <p className="eyebrow">ENTERPRISE KNOWLEDGE</p>
              <h1>
                {tab === "search"
                  ? "Find answers you can trace"
                  : tab === "documents"
                    ? "Document library"
                    : "Retrieval evaluation"}
              </h1>
              <p>Grounded in your sources. Scoped to your permissions.</p>
            </div>
            <button onClick={() => setUploadOpen(true)}>
              <Upload size={17} />
              Upload document
            </button>
          </div>
          {error && (
            <div role="alert" className="error">
              {error}
            </div>
          )}
          <section className="metrics">
            <article>
              <div>
                Accessible documents
                <Files size={18} />
              </div>
              <strong>{docs.length}</strong>
              <small>Authorized to your identity</small>
            </article>
            <article>
              <div>
                Indexed and ready
                <ShieldCheck size={18} />
              </div>
              <strong>{docs.filter((d) => d.status === "ready").length}</strong>
              <small>Current document versions</small>
            </article>
            <article>
              <div>
                Indexing errors
                <RefreshCw size={18} />
              </div>
              <strong>{docs.filter((d) => d.status === "error").length}</strong>
              <small>Review file or provider status</small>
            </article>
            <article>
              <div>
                Your groups
                <Network size={18} />
              </div>
              <strong>{me.groups.length}</strong>
              <small>{me.groups.join(" · ")}</small>
            </article>
          </section>
          {tab === "search" && (
            <>
              <section className="panel search-panel">
                <h2>Search your authorized knowledge</h2>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    void action(async () => {
                      const payload = { question: query };
                      setResults(
                        (await api("/search", "POST", payload)).results,
                      );
                      setAnswer(await api("/chat", "POST", payload));
                      setSearched(true);
                    });
                  }}
                >
                  <label htmlFor="question">Ask a question</label>
                  <div className="search-row">
                    <input
                      id="question"
                      required
                      minLength={3}
                      placeholder="How are travel expenses reimbursed?"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                    <button disabled={busy}>
                      <Search size={17} />
                      {busy ? "Searching…" : "Search & ask"}
                    </button>
                  </div>
                </form>
                <p className="muted">
                  Only authorized, current document chunks reach the answer
                  provider.
                </p>
              </section>
              {answer && (
                <section className="panel answer">
                  <div className="eyebrow">
                    {answer.uncertain
                      ? "INSUFFICIENT EVIDENCE"
                      : "GROUNDED RESPONSE"}
                  </div>
                  <p style={{ whiteSpace: "pre-wrap" }}>{answer.answer}</p>
                  <div className="citations">
                    {answer.citations.map(citationButton)}
                  </div>
                </section>
              )}
              {searched && (
                <section>
                  <h3>Retrieved sources · {results.length}</h3>
                  <div className="results">
                    {results.map((r) => (
                      <article className="panel result" key={r.chunk_id}>
                        <div>
                          <strong>{r.source}</strong>
                          <span className="status">
                            {((r.score || 0) * 100).toFixed(1)}% similarity
                          </span>
                        </div>
                        <p>{r.text}</p>
                        {citationButton(r)}
                      </article>
                    ))}
                  </div>
                  {!results.length && (
                    <div className="empty">
                      <Search />
                      <h3>No authorized evidence found</h3>
                      <p>
                        Try a different question or upload an accessible source.
                      </p>
                    </div>
                  )}
                </section>
              )}
            </>
          )}
          {tab === "documents" && (
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Source library</h2>
                  <p>Manage current versions and document access.</p>
                </div>
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() => void action(load)}
                >
                  <RefreshCw size={15} />
                  Refresh
                </button>
              </div>
              <div className="filters">
                <input
                  aria-label="Filter documents"
                  placeholder="Filter by filename or source…"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                />
              </div>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Document</th>
                      <th>Groups</th>
                      <th>Version</th>
                      <th>Index status</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {docs
                      .filter((d) =>
                        (d.filename + d.source)
                          .toLowerCase()
                          .includes(filter.toLowerCase()),
                      )
                      .map((d) => (
                        <tr key={d.id}>
                          <td>
                            <button
                              className="text-button"
                              onClick={() => {
                                setSelected(d);
                                setPermissionGroups(d.groups.join(","));
                              }}
                            >
                              {d.filename}
                            </button>
                            <small>{d.source}</small>
                          </td>
                          <td>{d.groups.join(", ") || "Owner only"}</td>
                          <td>v{d.version}</td>
                          <td>
                            <span
                              className={
                                "status " +
                                (d.status === "ready" ? "completed" : "failed")
                              }
                            >
                              {d.status}
                            </span>
                          </td>
                          <td>
                            <button
                              className="icon-button"
                              aria-label={`Download ${d.filename}`}
                              onClick={() => void action(() => download(d))}
                            >
                              <Download size={18} />
                            </button>
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
              {!docs.length && (
                <div className="empty">
                  <Files />
                  <h3>No documents available</h3>
                  <p>
                    Upload a source or ask its owner to grant your group access.
                  </p>
                </div>
              )}
            </section>
          )}
          {tab === "evaluation" && (
            <section className="panel search-panel">
              <h2>Recorded retrieval runs</h2>
              <p>
                Run the evaluation script to measure actual vector retrieval,
                citation validity and authorization. Reports are scoped to this
                tenant.
              </p>
              {reports.map((r) => (
                <article key={r.id}>
                  <h3>{new Date(r.created_at).toLocaleString()}</h3>
                  <pre>{JSON.stringify(r.report, null, 2)}</pre>
                </article>
              ))}
              {!reports.length && (
                <p className="notice">
                  No evaluation reports recorded for this tenant.
                </p>
              )}
            </section>
          )}
        </main>
      </div>
      <Dialog.Root open={uploadOpen} onOpenChange={setUploadOpen}>
        <Dialog.Portal>
          <Dialog.Overlay className="overlay" />
          <Dialog.Content className="dialog">
            <Dialog.Title>Upload a document</Dialog.Title>
            <Dialog.Description>
              PDF, DOCX, Markdown or TXT. Up to 8 MiB. Synthetic data only.
            </Dialog.Description>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void action(async () => {
                  if (!file) throw new Error("Select a file");
                  const data = new FormData();
                  data.append("file", file);
                  data.append("groups", groups);
                  data.append("source", source);
                  const doc = await api("/documents", "POST", data);
                  setUploadOpen(false);
                  await load();
                  if (doc.status === "error") setError(doc.error);
                  setTab("documents");
                });
              }}
            >
              <label htmlFor="file">Document file</label>
              <input
                id="file"
                type="file"
                accept=".pdf,.docx,.txt,.md"
                required
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
              <label htmlFor="groups">Allowed groups (comma separated)</label>
              <input
                id="groups"
                value={groups}
                onChange={(e) => setGroups(e.target.value)}
              />
              <label htmlFor="source">Source reference</label>
              <input
                id="source"
                value={source}
                onChange={(e) => setSource(e.target.value)}
                placeholder="hr/travel-policy"
              />
              <button disabled={busy}>
                {busy ? "Indexing…" : "Upload and index"}
              </button>
            </form>
            <Dialog.Close className="close" aria-label="Close">
              <X />
            </Dialog.Close>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      <Dialog.Root
        open={!!selected}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="overlay" />
          <Dialog.Content className="dialog">
            <Dialog.Title>{selected?.filename}</Dialog.Title>
            <Dialog.Description>
              Document metadata, current version and permissions.
            </Dialog.Description>
            {selected && (
              <>
                <pre>{JSON.stringify(selected, null, 2)}</pre>
                {(me.role === "admin" || selected.owner === me.user) && (
                  <>
                    <label htmlFor="permissions">Allowed groups</label>
                    <input
                      id="permissions"
                      value={permissionGroups}
                      onChange={(e) => setPermissionGroups(e.target.value)}
                    />
                    <button
                      disabled={busy}
                      onClick={() =>
                        void action(async () => {
                          setSelected(
                            await api(
                              `/documents/${selected.id}/permissions`,
                              "PUT",
                              {
                                groups: permissionGroups
                                  .split(",")
                                  .map((s) => s.trim())
                                  .filter(Boolean),
                              },
                            ),
                          );
                          await load();
                        })
                      }
                    >
                      Save permissions
                    </button>
                    <label htmlFor="replacement">
                      Replace document (increments version)
                    </label>
                    <input
                      id="replacement"
                      type="file"
                      accept=".pdf,.docx,.txt,.md"
                      disabled={busy}
                      onChange={(e) => {
                        const next = e.target.files?.[0];
                        if (next)
                          void action(async () => {
                            const form = new FormData();
                            form.append("file", next);
                            setSelected(
                              await api(
                                "/documents/" + selected.id,
                                "PUT",
                                form,
                              ),
                            );
                            await load();
                          });
                      }}
                    />
                    <button
                      className="secondary"
                      disabled={busy}
                      onClick={() => {
                        if (
                          window.confirm(
                            "Delete this synthetic document and its chunks?",
                          )
                        )
                          void action(async () => {
                            await api("/documents/" + selected.id, "DELETE");
                            setSelected(null);
                            await load();
                          });
                      }}
                    >
                      <Trash2 size={16} />
                      Delete document
                    </button>
                  </>
                )}
              </>
            )}
            <Dialog.Close className="close" aria-label="Close">
              <X />
            </Dialog.Close>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      <Dialog.Root
        open={!!citation}
        onOpenChange={(open) => {
          if (!open) setCitation(null);
        }}
      >
        <Dialog.Portal>
          <Dialog.Overlay className="overlay" />
          <Dialog.Content className="dialog">
            <Dialog.Title>Source citation</Dialog.Title>
            <Dialog.Description>
              {citation?.source} · version {citation?.version}
            </Dialog.Description>
            <p>{citation?.text}</p>
            <Dialog.Close className="close" aria-label="Close">
              <X />
            </Dialog.Close>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  );
}
if (document.getElementById("root"))
  createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
