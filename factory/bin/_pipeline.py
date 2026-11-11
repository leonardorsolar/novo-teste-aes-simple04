"""Read, resolve and validate factory/pipeline.yaml. Standard library only.

The same YAML subset is parsed by the page (js/yaml.js); scripts/test-yaml.mjs (in the
aes-simple repo) runs both on the same fixtures so they can't drift. Supported: block maps and lists, flow
[a, b] and {a: b} (may span lines), quoted and plain scalars, comments.
Not supported (and refused): anchors, aliases, tags, multi-line strings.
"""

import copy
import json
import os
import re
from pathlib import Path

KINDS = ("agent", "skill", "script", "human", "ci")
SPECIAL = {"@next", "@done", "@human", "@wait-author", "@rejected"}
EFFECTS = {"route", "worktree", "comment-issue", "pushed"}
STEP_KEYS = {"phase", "label", "run", "prompt", "reads", "writes", "next", "after", "group", "needs",
             "starts_round", "required", "confirm", "port", "description"}
RUN_KEYS = set(KINDS) | {"model", "resume"}
TOP_KEYS = {"version", "project", "defaults", "approval", "approval_modes", "phases", "steps",
            "profiles", "cycles", "routing", "prices"}
CYCLE_KEYS = {"label", "profile", "profiles", "approval", "override", "description"}
# description/local: a task started on the page without GitHub (local: true) carries its own text
TASK_KEYS = {"key", "title", "issue", "description", "local", "cycle", "profile", "approval", "active", "steps"}
TASK_STEP_KEYS = {"run", "prompt", "notes"}


class YamlError(Exception):
    pass


class Invalid(Exception):
    pass


# ---- YAML subset ------------------------------------------------------------


def _strip_comment(line):
    q, skip = None, False
    for i, c in enumerate(line):
        if skip:
            skip = False
        elif q:
            if c == "\\" and q == '"':
                skip = True
            elif c == q:
                q = None
        elif c in "\"'" and (i == 0 or line[i - 1] in " \t[{,:-"):
            q = c
        elif c == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i]
    return line


def _depth(s):
    d, q, skip = 0, None, False
    for i, c in enumerate(s):
        if skip:
            skip = False
        elif q:
            if c == "\\" and q == '"':
                skip = True
            elif c == q:
                q = None
        elif c in "\"'" and (i == 0 or s[i - 1] in " \t[{,:"):
            q = c
        elif c in "[{":
            d += 1
        elif c in "]}":
            d -= 1
    return d


def _scalar(s, where):
    s = s.strip()
    if not s:
        return None
    if s[0] == '"':
        if len(s) < 2 or s[-1] != '"':
            raise YamlError(f"{where}: aspas sem fechar: {s}")
        return json.loads(s)
    if s[0] == "'":
        if len(s) < 2 or s[-1] != "'":
            raise YamlError(f"{where}: aspas sem fechar: {s}")
        return s[1:-1].replace("''", "'")
    if s[0] in "&*!|>":
        raise YamlError(f"{where}: '{s[0]}' não é suportado (sem âncoras, tags ou texto multilinha)")
    if s in ("true", "false"):
        return s == "true"
    if s in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    return s


def _flow(s, i, where):
    """Parse a flow value starting at s[i]; returns (value, next index)."""
    def ws(i):
        while i < len(s) and s[i] in " \t":
            i += 1
        return i

    def quoted(i):
        q = s[i]
        j = i + 1
        while j < len(s):
            if q == '"' and s[j] == "\\":
                j += 2
                continue
            if s[j] == q:
                if q == "'" and j + 1 < len(s) and s[j + 1] == "'":
                    j += 2
                    continue
                return _scalar(s[i:j + 1], where), j + 1
            j += 1
        raise YamlError(f"{where}: aspas sem fechar")

    def value(i, stops):
        i = ws(i)
        if i >= len(s):
            raise YamlError(f"{where}: lista ou mapa sem fechar")
        if s[i] in "[{":
            return _flow(s, i, where)
        if s[i] in "\"'":
            return quoted(i)
        j = i
        while j < len(s) and s[j] not in stops:
            j += 1
        return _scalar(s[i:j], where), j

    i = ws(i)
    if s[i] == "[":
        out, i = [], ws(i + 1)
        if i < len(s) and s[i] == "]":
            return out, i + 1
        while True:
            v, i = value(i, ",]")
            out.append(v)
            i = ws(i)
            if i >= len(s):
                raise YamlError(f"{where}: '[' sem fechar")
            if s[i] == "]":
                return out, i + 1
            if s[i] != ",":
                raise YamlError(f"{where}: esperava ',' ou ']' em: {s}")
            i += 1
    if s[i] == "{":
        out, i = {}, ws(i + 1)
        if i < len(s) and s[i] == "}":
            return out, i + 1
        while True:
            i = ws(i)
            if s[i] in "\"'":
                k, i = quoted(i)
            else:
                j = i
                while j < len(s) and s[j] not in ":,}":
                    j += 1
                k, i = s[i:j].strip(), j
            i = ws(i)
            if i >= len(s) or s[i] != ":":
                raise YamlError(f"{where}: esperava ':' depois de {k!r} em: {s}")
            if str(k) in out:
                raise YamlError(f"{where}: chave repetida {k!r}")
            v, i = value(i + 1, ",}")
            out[str(k)] = v
            i = ws(i)
            if i >= len(s):
                raise YamlError(f"{where}: '{{' sem fechar")
            if s[i] == "}":
                return out, i + 1
            if s[i] != ",":
                raise YamlError(f"{where}: esperava ',' ou '}}' em: {s}")
            i += 1
    raise YamlError(f"{where}: valor inválido: {s}")


def _value(s, where):
    s = s.strip()
    if s and s[0] in "[{":
        v, i = _flow(s, 0, where)
        if s[i:].strip():
            raise YamlError(f"{where}: sobrou texto depois de fechar: {s[i:].strip()}")
        return v
    return _scalar(s, where)


def _split_key(c):
    """'key: rest' → (key, rest); None when the line isn't a map entry."""
    if c[0] in "\"'":
        q = c[0]
        j = c.find(q, 1)
        if j < 0 or c[j + 1:j + 2] != ":":
            return None
        return c[1:j], c[j + 2:].strip()
    if c[0] in "[{":
        return None
    m = re.match(r"([^:#\[\]{},]+?):(\s+|$)", c)
    if not m:
        return None
    return m.group(1).strip(), c[m.end():].strip()


def parse_yaml(text, name="pipeline.yaml"):
    raw = text.splitlines()
    lines, i = [], 0
    while i < len(raw):
        line = _strip_comment(raw[i]).rstrip()
        if not line.strip():
            i += 1
            continue
        lead = line[:len(line) - len(line.lstrip())]
        if "\t" in lead:
            raise YamlError(f"{name}:{i + 1}: use espaços, não tab, para indentar")
        if line.strip() == "---":
            i += 1
            continue
        start, content = i, line.strip()
        while _depth(content) > 0:
            i += 1
            if i >= len(raw):
                raise YamlError(f"{name}:{start + 1}: '[' ou '{{' sem fechar")
            content += " " + _strip_comment(raw[i]).strip()
        lines.append([start + 1, len(lead), content])
        i += 1
    if not lines:
        return {}

    def where(ln):
        return f"{name}:{ln}"

    def is_item(l):
        return l[2] == "-" or l[2].startswith("- ")

    def block(pos, indent):
        return seq(pos, indent) if is_item(lines[pos]) else mapping(pos, indent)

    def child(pos, indent):
        """Value of a 'key:' with nothing after it."""
        if pos < len(lines) and (lines[pos][1] > indent or (lines[pos][1] == indent and is_item(lines[pos]))):
            return block(pos, lines[pos][1])
        return None, pos

    def mapping(pos, indent):
        out = {}
        while pos < len(lines) and lines[pos][1] == indent and not is_item(lines[pos]):
            ln, _, c = lines[pos]
            kv = _split_key(c)
            if not kv:
                raise YamlError(f"{where(ln)}: esperava 'chave: valor', veio: {c}")
            k, rest = kv
            if k in out:
                raise YamlError(f"{where(ln)}: chave repetida {k!r}")
            if rest:
                out[k] = _value(rest, where(ln))
                pos += 1
            else:
                out[k], pos = child(pos + 1, indent)
        if pos < len(lines) and lines[pos][1] > indent:
            raise YamlError(f"{where(lines[pos][0])}: indentação inesperada")
        return out, pos

    def seq(pos, indent):
        out = []
        while pos < len(lines) and lines[pos][1] == indent and is_item(lines[pos]):
            ln, _, c = lines[pos]
            rest = c[1:].strip()
            if not rest:
                v, pos = child(pos + 1, indent)
                out.append(v)
                continue
            kv = _split_key(rest)
            if kv:
                sub = indent + len(c) - len(c[1:].lstrip())
                lines[pos] = [ln, sub, rest]
                v, pos = mapping(pos, sub)
                out.append(v)
            else:
                out.append(_value(rest, where(ln)))
                pos += 1
        if pos < len(lines) and lines[pos][1] > indent:
            raise YamlError(f"{where(lines[pos][0])}: indentação inesperada")
        return out, pos

    value, pos = block(0, lines[0][1])
    if pos != len(lines):
        raise YamlError(f"{where(lines[pos][0])}: indentação inesperada")
    return value


# ---- Load and resolve ---------------------------------------------------------


def load(repo):
    path = Path(repo) / "factory" / "pipeline.yaml"
    if not path.exists():
        raise Invalid(f"{path} não existe")
    return parse_yaml(path.read_text(), "factory/pipeline.yaml")


def load_task(repo, issue):
    """The page's factory/tasks/<KEY>.yaml for this issue, or None."""
    d = Path(repo) / "factory" / "tasks"
    if not d.exists():
        return None
    for p in sorted(d.glob("*.yaml")):
        t = parse_yaml(p.read_text(), f"factory/tasks/{p.name}") or {}
        if str(t.get("issue")) == str(issue):
            t["_file"] = f"factory/tasks/{p.name}"
            return t
    return None


def load_task_key(repo, key):
    """factory/tasks/<key>.yaml, or None. The key is a page task key like WORK-1."""
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", str(key)):
        return None
    p = Path(repo) / "factory" / "tasks" / f"{key}.yaml"
    if not p.exists():
        return None
    t = parse_yaml(p.read_text(), f"factory/tasks/{p.name}") or {}
    t["_file"] = f"factory/tasks/{p.name}"
    t.setdefault("key", key)
    return t


def local_tasks(repo):
    """Tasks the page started without GitHub: `local: true` and no issue. Unreadable files are skipped."""
    d = Path(repo) / "factory" / "tasks"
    out = []
    for p in sorted(d.glob("*.yaml")) if d.exists() else []:
        try:
            t = parse_yaml(p.read_text(), f"factory/tasks/{p.name}") or {}
        except YamlError:
            continue
        if t.get("local") is True and not t.get("issue"):
            t["_file"] = f"factory/tasks/{p.name}"
            t.setdefault("key", p.stem)
            out.append(t)
    return out


def kind_of(run):
    """The executor kind of a `run`. `{skill: x, agent: y}` = skill x run by agent y."""
    kinds = [k for k in KINDS if k in (run or {})]
    if set(kinds) == {"skill", "agent"}:
        return "skill"
    return kinds[0] if len(kinds) == 1 else None


def ref_of(run):
    k = kind_of(run)
    return run[k] if k else None


def _merge_step(step, patch):
    out = dict(step)
    for k, v in (patch or {}).items():
        out[k] = copy.deepcopy(v)  # `run` is replaced whole: one executor at a time
    return out


def resolve(cfg, cycle=None, profile=None, task=None):
    """The job's frozen pipeline: steps after cycle and task overrides, which are on, approval."""
    task = task or {}
    if not cfg["cycles"]:
        raise Invalid("nenhum ciclo configurado: crie um ou importe um JSON em Configurações da fábrica")
    cycle = cycle or task.get("cycle") or (cfg.get("defaults") or {}).get("cycle")
    if cycle not in cfg["cycles"]:
        raise Invalid(f"ciclo {cycle!r} não existe em cycles ({', '.join(cfg['cycles'])})")
    cyc = cfg["cycles"][cycle]
    steps = {sid: dict(s) for sid, s in cfg["steps"].items()}
    for sid, patch in (cyc.get("override") or {}).items():
        steps[sid] = _merge_step(steps[sid], patch)
    for sid, patch in (task.get("steps") or {}).items():
        if sid in steps:
            steps[sid] = _merge_step(steps[sid], {k: v for k, v in patch.items() if k in ("run", "prompt")})
            if patch.get("notes"):
                steps[sid]["notes"] = patch["notes"]
    prof = profile or task.get("profile") or cyc.get("profile")
    offered = cyc.get("profiles")
    if offered and prof not in ("auto", "custom", None) and prof not in offered and not task.get("active"):
        raise Invalid(f"o ciclo {cycle!r} não oferece o perfil {prof!r} (perfis: {', '.join(offered)})")
    active, fixed = None, False
    if task.get("active"):
        active, fixed = [s for s in steps if s in task["active"]], True
        prof = prof if prof in cfg["profiles"] else "custom"
    elif prof and prof != "auto":
        if prof not in cfg["profiles"]:
            raise Invalid(f"perfil {prof!r} não existe em profiles")
        active = [s for s in steps if s in cfg["profiles"][prof]["steps"]]
    approval = task.get("approval") or cyc.get("approval") or cfg["approval"]
    # etapas do ciclo (perfis que ele oferece): o roteamento global não liga etapas de outros ciclos
    scope = None
    if offered:
        own = {s for p in offered if p in cfg["profiles"] for s in cfg["profiles"][p].get("steps") or []}
        scope = [s for s in steps if s in own]
    return {
        "cycle": cycle, "profile": None if prof == "auto" else prof, "fixed": fixed, "scope": scope,
        "approval": approval, "pause_after": cfg["approval_modes"][approval]["pause_after"],
        "order": list(steps), "steps": steps,
        # before routing, only the first step runs (intake decides the rest)
        "active": active if active is not None else [next(iter(steps))],
        "routed": active is not None,
        "models": {}, "task": task.get("_file"),
        # executors the task chose by hand: routing never changes their model
        "pinned": [sid for sid, patch in (task.get("steps") or {}).items() if "run" in (patch or {})],
    }


def route(cfg, lock, intake):
    """After intake ACCEPT: choose the profile (when auto) and add/assign routed steps."""
    r = cfg.get("routing") or {}
    if not lock["routed"]:
        prof = (r.get("route_to_profile") or {}).get((intake.get("route") or "").lower()) or r.get("default_profile")
        offered = (cfg["cycles"].get(lock["cycle"]) or {}).get("profiles")
        if offered and prof not in offered:  # o ciclo só oferece estes perfis
            prof = offered[0]
        if prof not in cfg["profiles"]:
            raise Invalid(f"routing escolheu o perfil {prof!r}, que não existe")
        lock["profile"] = prof
        lock["active"] = [s for s in lock["order"] if s in cfg["profiles"][prof]["steps"]]
        lock["routed"] = True
    extra = {}
    risk = intake.get("risk")
    # sem tabela de risco/superfícies no projeto (ex.: fábrica montada do zero), o roteamento não liga nada
    if risk and (r.get("risk") or {}):
        if risk not in (r.get("risk") or {}):
            raise Invalid(f"risk {risk!r} não está em routing.risk ({', '.join(r.get('risk') or {})})")
        extra.update(r["risk"][risk])
    for s in (intake.get("surfaces") or []) if (r.get("surfaces") or {}) else []:
        if s not in (r.get("surfaces") or {}):
            raise Invalid(f"surface {s!r} não está em routing.surfaces ({', '.join(r.get('surfaces') or {})})")
        extra.update(r["surfaces"][s])
    on = set(lock["active"])
    for sid, model in extra.items():
        if sid not in lock["steps"]:
            raise Invalid(f"routing cita a etapa {sid!r}, que não existe")
        if lock.get("scope") is not None and sid not in lock["scope"]:
            continue  # etapa de outro ciclo
        if not lock["fixed"]:
            on.add(sid)
        if sid not in lock.get("pinned", []):
            lock["models"][sid] = model
    lock["active"] = [s for s in lock["order"] if s in on]
    return lock


# ---- Graph over the active steps -----------------------------------------------


def unit_of(lock, sid):
    """A step's execution unit: its group (the active members, in order) or itself."""
    g = lock["steps"][sid].get("group")
    if not g:
        return sid, [sid]
    return g, [s for s in lock["active"] if lock["steps"][s].get("group") == g]


def unit_by_name(lock, name):
    if name in lock["steps"] and name in lock["active"]:
        return unit_of(lock, name)
    members = [s for s in lock["active"] if lock["steps"][s].get("group") == name]
    return (name, members) if members else (None, [])


def first_active_from(lock, sid):
    """sid if it's on, else the next step that is on (None past the end)."""
    order = lock["order"]
    for s in order[order.index(sid):]:
        if s in lock["active"]:
            return s
    return None


def after_unit(lock, members):
    last = max(lock["order"].index(m) for m in members)
    rest = lock["order"][last + 1:]
    return first_active_from(lock, rest[0]) if rest else None


def target(lock, members, dest):
    """Resolve a destination from `next` to ('step', id, is_loop) or ('special', name, False)."""
    if dest == "@next":
        nxt = after_unit(lock, members)
        return ("step", nxt, False) if nxt else ("special", "@done", False)
    if dest in SPECIAL:
        return ("special", dest, False)
    s = first_active_from(lock, dest)
    if s is None:
        return ("special", "@done", False)
    loop = lock["order"].index(s) <= min(lock["order"].index(m) for m in members)
    return ("step", s, loop)


def model_of(lock, sid):
    return lock["models"].get(sid) or (lock["steps"][sid].get("run") or {}).get("model")


def plan_lines(lock):
    """Human-readable order of a resolved pipeline (factory plan)."""
    out, seen = [], set()
    for sid in lock["active"]:
        if sid in seen:
            continue
        name, members = unit_of(lock, sid)
        seen.update(members)
        parts = []
        for m in members:
            st = lock["steps"][m]
            run = st.get("run") or {}
            k = kind_of(run)
            model = model_of(lock, m)
            parts.append(f"{m} ({k}: {run.get(k)}{', ' + model if model else ''})")
        routes = []
        for verdict, dest in (lock["steps"][members[0]].get("next") or {}).items():
            kind, t, loop = target(lock, members, dest)
            routes.append(f"{verdict} → {t}{' (volta)' if loop else ''}")
        head = f"[{name}] " if len(members) > 1 or name != members[0] else ""
        out.append(f"{head}{' + '.join(parts)}\n      {' | '.join(routes)}")
    return out


# ---- Validation ---------------------------------------------------------------


def required_for(cfg):
    """Profile id -> required steps it must contain.

    `required` is scoped by cycle: a profile listed in a cycle's `profiles:` must contain the required
    steps used by that cycle's profiles. Profiles no cycle lists keep the original rule (every required
    step), except steps used only by listed profiles (another cycle's steps)."""
    steps, profs = cfg.get("steps") or {}, cfg.get("profiles") or {}
    req = [s for s, st in steps.items() if isinstance(st, dict) and st.get("required")]
    owners = {}
    for cyc in (cfg.get("cycles") or {}).values():
        if isinstance(cyc, dict) and isinstance(cyc.get("profiles"), list):
            for pid in cyc["profiles"]:
                owners.setdefault(pid, []).append(cyc["profiles"])
    def used(pids):
        return {s for pid in pids if pid in profs for s in (profs[pid].get("steps") or [])}
    unclaimed = [pid for pid in profs if pid not in owners]
    only_claimed = used(owners) - used(unclaimed)
    out = {}
    for pid in profs:
        if pid in owners:
            scope = set().union(*(used(lst) for lst in owners[pid]))
            out[pid] = [s for s in req if s in scope]
        else:
            out[pid] = [s for s in req if s not in only_claimed]
    return out


def validate(cfg, repo=None):
    """(errors, warnings) for a parsed pipeline.yaml. With repo, also checks the files it names."""
    errors, warns = [], []
    E, W = errors.append, warns.append
    if not isinstance(cfg, dict):
        return ["o arquivo não é um mapa"], []
    for k in cfg:
        if k not in TOP_KEYS:
            E(f"chave desconhecida no topo: {k!r}")
    for k in ("project", "defaults", "approval", "approval_modes", "phases", "steps", "profiles", "cycles"):
        if k not in cfg:
            E(f"falta a seção {k!r}")
    if errors:
        return errors, warns
    steps, phases = cfg["steps"], [p.get("id") for p in cfg["phases"]]
    order = list(steps)
    if cfg["approval"] not in cfg["approval_modes"]:
        E(f"approval {cfg['approval']!r} não está em approval_modes")
    for mid, m in cfg["approval_modes"].items():
        pa = m.get("pause_after")
        if pa != "all" and not isinstance(pa, list):
            E(f"approval_modes.{mid}.pause_after deve ser 'all' ou uma lista")
        elif isinstance(pa, list):
            for s in pa:
                if s not in steps:  # pausa depois de uma etapa que não existe: nunca pausa
                    W(f"approval_modes.{mid}.pause_after cita a etapa {s!r}, que não existe")
    groups = {}
    for i, (sid, st) in enumerate(steps.items()):
        p = f"steps.{sid}"
        if not isinstance(st, dict):
            E(f"{p}: deve ser um mapa")
            continue
        for k in st:
            if k not in STEP_KEYS:
                E(f"{p}: chave desconhecida {k!r} (erro de digitação?)")
        if st.get("phase") not in phases:
            E(f"{p}.phase: {st.get('phase')!r} não está em phases")
        run = st.get("run")
        if not isinstance(run, dict) or not kind_of(run):
            E(f"{p}.run: precisa de exatamente um de {', '.join(KINDS)}")
        else:
            for k in run:
                if k not in RUN_KEYS:
                    E(f"{p}.run: chave desconhecida {k!r}")
        if not st.get("writes"):
            E(f"{p}: falta writes (o arquivo que prova que a etapa terminou)")
        on = st.get("next")
        if not isinstance(on, dict) or not on:
            E(f"{p}: falta next (veredito → destino)")
            on = {}
        for verdict, dest in on.items():
            if dest in SPECIAL:
                continue
            if dest not in steps:
                E(f"{p}.next.{verdict}: destino {dest!r} não existe")
            elif order.index(dest) <= i and not steps[dest].get("starts_round"):
                E(f"{p}.next.{verdict}: volta para {dest!r}, que não tem starts_round: o laço não teria limite")
        for eff in st.get("after") or []:
            if eff not in EFFECTS and not str(eff).startswith("factory/"):
                E(f"{p}.after: {eff!r} não é um efeito conhecido ({', '.join(sorted(EFFECTS))}) nem um script em factory/")
        for n in st.get("needs") or []:
            if n not in steps:
                E(f"{p}.needs: {n!r} não existe")
            elif order.index(n) >= i:
                E(f"{p}.needs: {n!r} vem depois desta etapa")
        if st.get("group"):
            groups.setdefault(st["group"], []).append((i, sid))
    for g, members in groups.items():
        idx = [i for i, _ in members]
        if idx != list(range(idx[0], idx[0] + len(idx))):
            E(f"grupo {g!r}: as etapas precisam estar seguidas em steps")
        keys = {tuple(sorted((steps[s].get("next") or {}).items())) for _, s in members}
        if len(keys) > 1:
            E(f"grupo {g!r}: todas as etapas precisam ter o mesmo next")
        if g in steps:
            E(f"grupo {g!r} tem o mesmo nome de uma etapa")
    need = required_for(cfg)
    for pid, prof in cfg["profiles"].items():
        ps = prof.get("steps") or []
        for s in ps:
            if s not in steps:
                E(f"profiles.{pid}: etapa {s!r} não existe")
        for s in need.get(pid, []):
            if s not in ps:
                E(f"profiles.{pid}: falta a etapa obrigatória {s!r}")
    for cid, cyc in cfg["cycles"].items():
        for k in cyc:
            if k not in CYCLE_KEYS:
                E(f"cycles.{cid}: chave desconhecida {k!r}")
        pr = cyc.get("profile")
        if pr != "auto" and pr not in cfg["profiles"]:
            E(f"cycles.{cid}.profile: {pr!r} não existe (use um perfil ou auto)")
        offered = cyc.get("profiles")
        if offered is not None:
            if not isinstance(offered, list) or not offered:
                E(f"cycles.{cid}.profiles: deve ser uma lista de perfis")
            else:
                for x in offered:
                    if x not in cfg["profiles"]:
                        E(f"cycles.{cid}.profiles: perfil {x!r} não existe")
                if pr != "auto" and pr not in offered:
                    E(f"cycles.{cid}.profile: {pr!r} precisa estar em cycles.{cid}.profiles")
        if cyc.get("approval") and cyc["approval"] not in cfg["approval_modes"]:
            E(f"cycles.{cid}.approval: {cyc['approval']!r} não existe")
        for sid, patch in (cyc.get("override") or {}).items():
            if sid not in steps:
                E(f"cycles.{cid}.override: etapa {sid!r} não existe")
            elif "run" in patch and not kind_of(patch["run"]):
                E(f"cycles.{cid}.override.{sid}.run: precisa de exatamente um executor")
    if cfg["cycles"] and (cfg["defaults"] or {}).get("cycle") not in cfg["cycles"]:
        E(f"defaults.cycle: {cfg['defaults'].get('cycle')!r} não existe em cycles")
    r = cfg.get("routing") or {}
    for table in ("risk", "surfaces"):
        for k, m in (r.get(table) or {}).items():
            for sid in m:
                if sid not in steps:
                    E(f"routing.{table}.{k}: etapa {sid!r} não existe")
    for k, pid in (r.get("route_to_profile") or {}).items():
        if pid not in cfg["profiles"]:
            E(f"routing.route_to_profile.{k}: perfil {pid!r} não existe")
    if r and r.get("default_profile") not in cfg["profiles"]:
        E(f"routing.default_profile: {r.get('default_profile')!r} não existe")
    used = {s for p in cfg["profiles"].values() for s in p.get("steps") or []}
    for s in steps:
        if s not in used:
            W(f"a etapa {s!r} não está em nenhum perfil")
    if repo is not None:
        repo = Path(repo)
        good = {sid: st for sid, st in steps.items() if isinstance(st, dict)}
        runs = [(f"steps.{sid}", st["run"]) for sid, st in good.items() if isinstance(st.get("run"), dict)]
        runs += [(f"cycles.{cid}.override.{sid}", p["run"]) for cid, c in cfg["cycles"].items() if isinstance(c, dict)
                 for sid, p in (c.get("override") or {}).items() if isinstance(p, dict) and isinstance(p.get("run"), dict)]
        for where, run in runs:
            k, ref = kind_of(run), ref_of(run)
            agent = run.get("agent")
            if agent and not (repo / ".claude" / "agents" / f"{agent}.md").exists():
                E(f"{where}: agente {agent!r} não existe em .claude/agents/{agent}.md")
            if k == "skill" and not (repo / ".claude" / "skills" / str(ref) / "SKILL.md").exists():
                E(f"{where}: skill {ref!r} não existe em .claude/skills/{ref}/SKILL.md")
            elif k == "script":
                f = repo / str(ref)
                if not f.exists():
                    E(f"{where}: script {ref!r} não existe")
                elif not os.access(f, os.X_OK):
                    E(f"{where}: script {ref!r} sem permissão de execução (chmod +x {ref})")
        for sid, st in good.items():
            if st.get("prompt") and not (repo / st["prompt"]).exists():
                E(f"steps.{sid}.prompt: {st['prompt']!r} não existe")
            elif st.get("prompt") and not (repo / st["prompt"]).read_text().strip():
                W(f"steps.{sid}.prompt: {st['prompt']!r} está vazio")
            for eff in st.get("after") or []:
                if str(eff).startswith("factory/") and not (repo / eff).exists():
                    E(f"steps.{sid}.after: script {eff!r} não existe")
        checks = cfg["project"].get("checks")
        if steps and (not checks or not (repo / checks).exists()):
            E(f"project.checks: {checks!r} não existe")
    return errors, warns


def validate_task(cfg, task):
    errors = []
    for k in task:
        if k not in TASK_KEYS and not k.startswith("_"):
            errors.append(f"chave desconhecida {k!r}")
    if task.get("cycle") and task["cycle"] not in cfg["cycles"]:
        errors.append(f"cycle {task['cycle']!r} não existe")
    if task.get("profile") and task["profile"] not in cfg["profiles"] and task["profile"] not in ("custom", "auto"):
        errors.append(f"profile {task['profile']!r} não existe")
    cyc = cfg["cycles"].get(task.get("cycle") or (cfg.get("defaults") or {}).get("cycle")) or {}
    if task.get("profile") and cyc.get("profiles") and task["profile"] not in cyc["profiles"] + ["custom", "auto"]:
        errors.append(f"profile {task['profile']!r} não é oferecido pelo ciclo (perfis: {', '.join(cyc['profiles'])})")
    if task.get("approval") and task["approval"] not in cfg["approval_modes"]:
        errors.append(f"approval {task['approval']!r} não existe")
    for s in task.get("active") or []:
        if s not in cfg["steps"]:
            errors.append(f"active: etapa {s!r} não existe")
    for s, patch in (task.get("steps") or {}).items():
        if s not in cfg["steps"]:
            errors.append(f"steps: etapa {s!r} não existe")
            continue
        for k in patch:
            if k not in TASK_STEP_KEYS:
                errors.append(f"steps.{s}: chave desconhecida {k!r}")
        if "run" in patch and not kind_of(patch["run"]):
            errors.append(f"steps.{s}.run: precisa de exatamente um executor")
    return errors
