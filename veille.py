#!/usr/bin/env python3
"""Veille automatique : lance les skills trader-skill et écrit un rapport en français.

    python3 veille.py matin    # actualités, déclarations du Congrès, nouveaux 13F
    python3 veille.py seance   # alertes de prix

Lit suivi.json (ce que tu suis), garde la mémoire dans etat/ (ce qui a déjà été vu)
et écrit le rapport dans rapport.md. Le workflow GitHub transforme rapport.md en
issue. Ce script ne passe jamais d'ordre.

Variables d'environnement :
    SKILLS_DIR          dossier du dépôt trader-skill (défaut : skills)
    SEC_USER_AGENT      "Ton Nom ton@email.com", exigé par la SEC
    TRADER_OFFLINE_DIR  tests seulement : lit les fichiers d'exemple au lieu d'Internet
"""

import datetime as dt
import json
import os
import subprocess
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.environ.get("SKILLS_DIR") or os.path.join(ICI, "skills")
ETAT = os.path.join(ICI, "etat")
OFFLINE = os.environ.get("TRADER_OFFLINE_DIR")
RAPPORT = os.path.join(ICI, "rapport.md")
TITRE = os.path.join(ICI, "titre.txt")

TAGS = {"earnings": "résultats", "analyst": "analystes", "legal": "justice", "deal": "rachat/fusion",
        "capital": "dividende/rachat d'actions", "people": "dirigeants", "risk": "risque"}
OPERATIONS = {"purchase": "achat", "sale": "vente", "partial sale": "vente partielle", "exchange": "échange"}
TITULAIRES = {"spouse": "conjoint", "joint": "commun", "dependent child": "enfant", "self": "l'élu(e)"}
TYPES = {"monte_a": "above", "descend_a": "below", "stop": "stop", "bouge_de": "pct_move",
         "ouverture": "opening_bell"}
PIED = ("_Rapport automatique (skills trader-skill, GitHub Actions). Données publiques, cours "
        "différés. Information, pas un conseil d'investissement : aucun ordre n'est passé ici._")


# ---------------------------------------------------------------- outils

def lire(chemin, defaut=None):
    try:
        with open(chemin, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return defaut


def ecrire(chemin, data):
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def skill(script, *args):
    """Lance un script de skill avec --json ; renvoie (données, erreur)."""
    cmd = [sys.executable, "-I", os.path.join(SKILLS, script)] + [str(a) for a in args]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=600, cwd=ICI)
    except subprocess.TimeoutExpired:
        return None, "%s : délai dépassé" % script
    try:
        return json.loads(p.stdout), None
    except ValueError:
        err = (p.stderr or p.stdout or "").strip().splitlines()
        return None, "%s : %s" % (script, err[-1] if err else "code %d" % p.returncode)


def suivi():
    s = lire(os.path.join(ICI, "suivi.json"))
    if not s:
        raise SystemExit("suivi.json manquant ou illisible (vérifie les virgules et les guillemets)")
    s["actions"] = [a.strip().upper() for a in s.get("actions", []) if a.strip()]
    return s


def heure_paris(iso):
    if not iso:
        return ""
    try:
        from zoneinfo import ZoneInfo
        t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return t.astimezone(ZoneInfo("Europe/Paris")).strftime("%d/%m %H:%M")
    except Exception:
        return iso[:16].replace("T", " ")


def montant(n):
    return "{:,.0f}".format(n).replace(",", " ")


# ---------------------------------------------------------------- matin

def actualites(s, notes):
    if not s["actions"]:
        return []
    args = ["--tickers"] + s["actions"] + ["--hours", 30, "--json", "--state", os.path.join(ETAT, "news.json"),
                                          "--config", os.path.join(ICI, "absent.json")]
    if OFFLINE:
        args += ["--offline", os.path.join(OFFLINE, "trader-news"), "--hours", 24 * 3650]
    data, err = skill("trader-news/news.py", *args)
    if err:
        notes.append("Actualités : " + err)
        return []
    notes += ["Actualités : " + n for n in data.get("notes", [])]
    items = [i for i in data["items"] if i.get("new")]
    if not items:
        return []
    out = ["## 📰 Actualités", ""]
    importants = [i for i in items if i.get("important")]
    if importants:
        out.append("**Dépôts officiels importants à la SEC**")
        for i in importants:
            out.append("- ⚠️ **%s** · %s · [%s](%s)" % (", ".join(i["touches"] or [i["ticker"]]),
                                                     heure_paris(i["time"]), i["title"], i["link"]))
        out.append("")
    par_action = {}
    for i in items:
        if not i.get("important"):
            par_action.setdefault((i["touches"] or [i["ticker"]])[0], []).append(i)
    for action in sorted(par_action):
        out.append("**%s**" % action)
        for i in par_action[action][:8]:
            tags = ", ".join(TAGS.get(t, t) for t in i.get("tags", []))
            src = "SEC" if i["kind"] == "filing" else i["source"]
            out.append("- %s · %s · [%s](%s)%s" % (heure_paris(i["time"]), src, i["title"], i["link"],
                                                  (" — _%s_" % tags) if tags else ""))
        if len(par_action[action]) > 8:
            out.append("- … et %d autre(s)" % (len(par_action[action]) - 8))
        out.append("")
    out.append("_Un titre est une piste, pas un fait : ouvre l'article avant d'agir._")
    out.append("")
    return out


def congres(s, notes):
    elus = s.get("elus", [])
    if not elus:
        return []
    tous = any(str(e).strip().lower() in ("tous", "*") for e in elus)
    args = ["new", "--json", "--state", os.path.join(ETAT, "pelosi.json"), "--pdf-dir",
            os.path.join(ICI, ".ptr-pdfs")]
    if tous:
        # tous les élus : seulement les déclarations des 3 derniers jours (sinon des centaines au départ)
        args += ["--since", (dt.date.today() - dt.timedelta(days=3)).isoformat()]
    else:
        for e in elus:
            args += ["--member", e]
    if s["actions"]:
        args += ["--tickers"] + s["actions"]
    if OFFLINE:
        args += ["--offline", os.path.join(OFFLINE, "trader-pelosi", "2026FD.zip"), "--year", 2026]
    else:
        args += ["--read"]
    data, err = skill("trader-pelosi/ptr.py", *args)
    if err:
        notes.append("Congrès : " + err)
        return []
    if not data.get("new"):
        return []
    reports = {r["filing"]["doc_id"]: r for r in data.get("reports", [])}
    out = ["## 🏛️ Nouvelles déclarations du Congrès", ""]
    suivies = []
    for f in data["new"]:
        rep = (reports.get(f["doc_id"]) or {}).get("report") or {}
        for r in rep.get("rows", []):
            if r.get("ticker") in s["actions"]:
                suivies.append("- ⭐ **%s** : %s de %s (%s), le %s" % (
                    f["name"], OPERATIONS.get(r.get("type_name"), r.get("type_name") or ""), r["ticker"],
                    r.get("amount") or "", r.get("date") or ""))
    if suivies:
        out += ["**Concernent tes actions**"] + suivies + [""]
    out.append("%d nouvelle(s) déclaration(s) :" % len(data["new"]))
    out.append("")
    for f in data["new"]:
        out.append("**%s** (%s) · déposée le %s · [PDF](%s)" % (f["name"], f["district"], f["filed"], f["url"]))
        rep = (reports.get(f["doc_id"]) or {}).get("report")
        if rep and rep.get("rows"):
            out.append("")
            out.append("| Date | Action | Opération | Titulaire | Montant | Délai |")
            out.append("| --- | --- | --- | --- | --- | --- |")
            for r in rep["rows"][:15]:
                action = r.get("ticker") or r.get("asset", "")[:30]
                if r.get("ticker") in s["actions"]:
                    action = "⭐ " + action
                op = OPERATIONS.get(r.get("type_name"), r.get("type_name") or "")
                if r.get("option"):
                    o = r["option"]
                    op += " (%d %s, prix d'exercice %g $, éch. %s)" % (o["contracts"], o["kind"], o["strike"],
                                                                     o["expires"])
                delai = r.get("days_to_disclose")
                out.append("| %s | %s | %s | %s | %s | %s |" % (
                    r.get("date") or "", action, op, TITULAIRES.get(r.get("owner_name"), r.get("owner_name") or ""),
                    r.get("amount") or "", "" if delai is None else "%d j%s" % (delai, " ⚠️" if r.get("late") else "")))
            if len(rep["rows"]) > 15:
                out.append("")
                out.append("… et %d autre(s) ligne(s) : voir le PDF." % (len(rep["rows"]) - 15))
        elif not OFFLINE:
            out.append("- Lecture automatique impossible : ouvre le PDF.")
        out.append("")
    out.append("_Déclarations publiques faites jusqu'à 45 jours après la transaction ; montants en "
               "fourchettes. ⭐ = une action que tu suis._")
    out.append("")
    return out


def fonds(s, notes):
    liste = s.get("fonds", [])
    if not liste:
        return []
    chemin = os.path.join(ETAT, "fonds.json")
    vus = lire(chemin, {})
    out = []
    off = ["--offline", os.path.join(OFFLINE, "trader-copycat")] if OFFLINE else []
    for f in liste:
        cik = str(f["cik"]).zfill(10)
        data, err = skill("trader-copycat/edgar13f.py", "filings", cik, "--limit", 1, "--json", *off)
        if err:
            notes.append("13F %s : %s" % (f.get("nom", cik), err))
            continue
        if not data.get("filings"):
            continue
        dernier = data["filings"][0]
        avant = vus.get(cik)
        vus[cik] = dernier["accession"]
        if avant is None:
            notes.append("13F %s : suivi activé (dernier rapport au %s, déposé le %s)."
                         % (f.get("nom") or data.get("filer"), dernier["period"], dernier["filed"]))
            continue
        if avant == dernier["accession"]:
            continue
        d, err = skill("trader-copycat/edgar13f.py", "diff", cik, "--combine", "--json", *off)
        out += ["## 📑 Nouveau 13F : %s" % (f.get("nom") or data.get("filer")), "",
                "Positions au %s, déposé le %s ([dépôt SEC](https://www.sec.gov/cgi-bin/browse-edgar?action="
                "getcompany&CIK=%s&type=13F-HR)). Comparaison avec le trimestre précédent :" % (
                    dernier["period"], dernier["filed"], cik), ""]
        if err:
            notes.append("13F %s : %s" % (f.get("nom", cik), err))
            continue
        groupes = [("NEW", "Nouvelles lignes"), ("SOLD OUT", "Vendues entièrement"),
                   ("ADDED", "Renforcées"), ("TRIMMED", "Allégées")]
        for code, nom in groupes:
            g = [c for c in d["changes"] if c["status"] == code and not c.get("put_call")][:10]
            if not g:
                continue
            out.append("**%s**" % nom)
            for c in g:
                pct = "" if c.get("change_pct") is None or code in ("NEW", "SOLD OUT") else " (%+.1f %%)" % c["change_pct"]
                out.append("- %s %s : %s → %s actions%s" % (c.get("ticker") or "?", c["issuer"],
                                                           montant(c["shares_before"]), montant(c["shares_after"]), pct))
            out.append("")
        out.append("_Nombre d'actions à deux fins de trimestre : ni les dates ni les prix des transactions. "
                   "C'est la société qui déclare, pas la personne connue._")
        out.append("")
    ecrire(chemin, vus)
    return out


def matin():
    s = suivi()
    notes = []
    corps = actualites(s, notes) + congres(s, notes) + fonds(s, notes)
    jour = dt.date.today().strftime("%d/%m/%Y")
    return ("Point du matin — %s" % jour, corps, notes)


# ---------------------------------------------------------------- séance

def regles(s):
    out = []
    for a in s.get("alertes", []):
        typ = TYPES.get(a.get("type"))
        if not typ:
            raise SystemExit("suivi.json : type d'alerte inconnu %r (choix : %s)" % (a.get("type"), ", ".join(TYPES)))
        r = {"type": typ}
        if typ == "opening_bell":
            r["id"] = "ouverture"
        else:
            r["symbol"] = str(a["action"]).upper()
            if typ == "pct_move":
                r["pct"] = float(a["pourcent"])
            else:
                r["price"] = float(a["prix"])
            r["id"] = "%s-%s-%s" % (r["symbol"].lower(), a["type"], r.get("price", r.get("pct")))
        if a.get("rearmer"):
            r["rearm"] = True
        if a.get("note"):
            r["note"] = a["note"]
        r["_fr"] = a
        out.append(r)
    return out


def texte_alerte(a, prix):
    t = a.get("type")
    cours = "" if prix is None else " — cours %.2f $" % prix
    if t == "monte_a":
        s = "%s est monté à %s $ ou plus%s" % (a["action"].upper(), a["prix"], cours)
    elif t in ("descend_a", "stop"):
        s = "%s est descendu à %s $ ou moins%s" % (a["action"].upper(), a["prix"], cours)
    elif t == "bouge_de":
        s = "%s a bougé de %s %% ou plus depuis la clôture d'hier%s" % (a["action"].upper(), a["pourcent"], cours)
    else:
        s = "La bourse de New York vient d'ouvrir"
    if a.get("note"):
        s += " (%s)" % a["note"]
    return s


def seance():
    s = suivi()
    notes = []
    rs = regles(s)
    if not rs:
        return ("", [], [])
    fichier = os.path.join(ICI, ".alerts.json")
    ecrire(fichier, {"rules": [{k: v for k, v in r.items() if k != "_fr"} for r in rs]})
    args = ["check", "--json", "--rules", fichier, "--state", os.path.join(ETAT, "alerts.json"),
            "--prices-out", os.path.join(ETAT, "prix.json")]
    if OFFLINE:
        args += ["--offline", os.path.join(OFFLINE, "trader-alerts")]
    data, err = skill("trader-alerts/alerts.py", *args)
    if err:
        return ("", [], ["Alertes : " + err])
    notes += ["Alertes : " + e for e in data.get("errors", [])]
    par_id = {r["id"]: r["_fr"] for r in rs}
    lignes = []
    for ring in data.get("rings", []):
        a = par_id.get(ring["id"])
        prix = data.get("quotes", {}).get(ring.get("symbol"))
        lignes.append("- 🔔 " + (texte_alerte(a, prix) if a else ring["message"]))
    if not lignes:
        return ("", [], notes)
    m = data["market"]
    corps = ["## 🔔 Alertes de prix", ""] + lignes + [
        "", "Bourse de New York : %s (%s heure de New York)." % ("ouverte" if m["open"] else "fermée",
                                                              m["now_new_york"]),
        "", "_Une alerte est une information, pas un ordre. Pour agir : page Propositions ou Passer un ordre "
            "de ton app, avec contrôle de risque et ton oui._", ""]
    noms = sorted({(par_id.get(r["id"]) or {}).get("action", "ouverture").upper() for r in data["rings"]})
    return ("Alerte — %s" % ", ".join(noms), corps, notes)


# ---------------------------------------------------------------- sortie

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode not in ("matin", "seance"):
        raise SystemExit("usage : veille.py matin | seance")
    titre, corps, notes = matin() if mode == "matin" else seance()
    for f in (RAPPORT, TITRE):
        if os.path.exists(f):
            os.remove(f)
    if corps:
        texte = corps
        if notes:
            texte += ["<details><summary>Notes techniques</summary>", ""] + ["- " + n for n in notes] + ["", "</details>", ""]
        texte.append(PIED)
        with open(RAPPORT, "w", encoding="utf-8") as fh:
            fh.write("\n".join(texte) + "\n")
        with open(TITRE, "w", encoding="utf-8") as fh:
            fh.write(titre)
        print("Rapport écrit : " + titre)
    else:
        print("Rien de nouveau.")
        for n in notes:
            print("note : " + n)
    # un problème technique est signalé une seule fois par jour, même sans rien de nouveau
    pannes = [n for n in notes if "suivi activé" not in n]
    if pannes and not corps:
        etat = lire(os.path.join(ETAT, "pannes.json"), {})
        jour = dt.date.today().isoformat()
        if etat.get(mode) != jour:
            etat[mode] = jour
            ecrire(os.path.join(ETAT, "pannes.json"), etat)
            with open(RAPPORT, "w", encoding="utf-8") as fh:
                fh.write("La veille « %s » a rencontré un problème :\n\n%s\n\nLe reste a fonctionné. "
                         "Si cela se répète plusieurs jours, regarde l'onglet Actions du dépôt.\n"
                         % (mode, "\n".join("- " + n for n in pannes)))
            with open(TITRE, "w", encoding="utf-8") as fh:
                fh.write("Veille : problème technique (%s)" % mode)


if __name__ == "__main__":
    main()
