"""Interface graphique Tkinter (entièrement en français)."""

import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import VERSION, journal
from . import libelles as L
from . import securite
from .rythme import MODE_HUMAIN, MODE_RAPIDE
from .saisie import ETAT_LIBELLE, Etat, MoteurSaisie, SurveillanceUrgence
from .texte import ErreurImportation, importer_fichier, texte_est_vide

LIBELLE_ETAT_WORD = {
    securite.ETAT_ACTIF: L.WORD_DETECTE,
    securite.ETAT_OUVERT_NON_ACTIF: L.WORD_OUVERT_NON_ACTIF,
    securite.ETAT_FERME: L.WORD_NON_DETECTE,
    securite.ETAT_NON_INSTALLE: L.WORD_NON_INSTALLE,
}
VITESSE_DEFAUT = {L.MODE_RAPIDE: 60, L.MODE_HUMAIN: 8}


class InfoBulle:
    def __init__(self, widget, texte):
        self.widget, self.texte, self.fenetre = widget, texte, None
        widget.bind("<Enter>", self._afficher)
        widget.bind("<Leave>", self._masquer)

    def _afficher(self, _):
        if self.fenetre:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.fenetre = tk.Toplevel(self.widget)
        self.fenetre.wm_overrideredirect(True)
        self.fenetre.wm_geometry(f"+{x}+{y}")
        tk.Label(self.fenetre, text=self.texte, background="#ffffe0", relief="solid",
                 borderwidth=1, wraplength=320, justify="left", padx=6, pady=3).pack()

    def _masquer(self, _):
        if self.fenetre:
            self.fenetre.destroy()
            self.fenetre = None


class Application:
    def __init__(self, racine: tk.Tk, moteur: MoteurSaisie):
        self.racine = racine
        self.moteur = moteur
        self.etat_word = securite.ETAT_FERME
        self.prochaine_verif_word = 0
        self.taille_groupe = tk.IntVar(value=4)
        self.journal_actif = tk.BooleanVar(value=False)

        racine.title(L.NOM_LOGICIEL)
        racine.geometry("860x700")
        racine.minsize(760, 620)
        self._construire()
        racine.protocol("WM_DELETE_WINDOW", self.quitter)
        self._sur_changement_mode()
        self._maj_compteur()
        self.racine.after(100, self._boucle_interface)

    # --- Construction ---

    def _construire(self):
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
        cadre = ttk.Frame(self.racine, padding=10)
        cadre.pack(fill="both", expand=True)
        cadre.columnconfigure(0, weight=1)
        cadre.rowconfigure(0, weight=1)

        # Zone A : texte
        zone_a = ttk.LabelFrame(cadre, text=L.ZONE_TEXTE, padding=6)
        zone_a.grid(row=0, column=0, sticky="nsew")
        zone_a.columnconfigure(0, weight=1)
        zone_a.rowconfigure(0, weight=1)
        self.zone_texte = tk.Text(zone_a, wrap="word", undo=True, font=("Segoe UI", 11), height=10)
        defilement = ttk.Scrollbar(zone_a, command=self.zone_texte.yview)
        self.zone_texte.configure(yscrollcommand=defilement.set)
        self.zone_texte.grid(row=0, column=0, sticky="nsew")
        defilement.grid(row=0, column=1, sticky="ns")
        self.zone_texte.bind("<<Modified>>", self._sur_modification)

        # Zone B : importation
        zone_b = ttk.LabelFrame(cadre, text=L.ZONE_IMPORT, padding=6)
        zone_b.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.btn_import_txt = ttk.Button(zone_b, text=L.BTN_IMPORT_TXT,
                                         command=lambda: self.importer([("txt", "*.txt")]))
        self.btn_import_docx = ttk.Button(zone_b, text=L.BTN_IMPORT_DOCX,
                                          command=lambda: self.importer([("docx", "*.docx")]))
        self.btn_import_txt.pack(side="left", padx=(0, 6))
        self.btn_import_docx.pack(side="left")

        # Zone C : paramètres
        zone_c = ttk.LabelFrame(cadre, text=L.ZONE_PARAMETRES, padding=6)
        zone_c.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        zone_c.columnconfigure(1, weight=1)

        ttk.Label(zone_c, text=L.LBL_MODE).grid(row=0, column=0, sticky="w")
        self.var_mode = tk.StringVar(value=L.MODE_RAPIDE)
        self.liste_mode = ttk.Combobox(zone_c, textvariable=self.var_mode, state="readonly",
                                       values=[L.MODE_RAPIDE, L.MODE_HUMAIN], width=20)
        self.liste_mode.grid(row=0, column=1, sticky="w", padx=6)
        self.liste_mode.bind("<<ComboboxSelected>>", lambda _: self._sur_changement_mode())
        InfoBulle(self.liste_mode, L.INFOBULLES["mode"])

        ttk.Label(zone_c, text=L.LBL_VITESSE).grid(row=1, column=0, sticky="w")
        self.var_vitesse = tk.IntVar(value=VITESSE_DEFAUT[L.MODE_RAPIDE])
        self.echelle_vitesse = ttk.Scale(zone_c, from_=1, to=200, variable=self.var_vitesse,
                                         command=lambda v: self.var_vitesse.set(int(float(v))))
        self.echelle_vitesse.grid(row=1, column=1, sticky="ew", padx=6)
        self.lbl_vitesse = ttk.Label(zone_c, width=5)
        self.lbl_vitesse.grid(row=1, column=2)
        InfoBulle(self.echelle_vitesse, L.INFOBULLES["vitesse"])

        ttk.Label(zone_c, text=L.LBL_INTENSITE).grid(row=2, column=0, sticky="w")
        self.var_intensite = tk.IntVar(value=5)
        self.echelle_intensite = ttk.Scale(zone_c, from_=0, to=10, variable=self.var_intensite,
                                           command=lambda v: self.var_intensite.set(int(float(v))))
        self.echelle_intensite.grid(row=2, column=1, sticky="ew", padx=6)
        self.lbl_intensite = ttk.Label(zone_c, width=5)
        self.lbl_intensite.grid(row=2, column=2)
        InfoBulle(self.echelle_intensite, L.INFOBULLES["intensite"])

        ttk.Label(zone_c, text=L.LBL_DELAI).grid(row=3, column=0, sticky="w")
        self.var_delai = tk.IntVar(value=5)
        self.champ_delai = ttk.Spinbox(zone_c, from_=1, to=60, textvariable=self.var_delai, width=6)
        self.champ_delai.grid(row=3, column=1, sticky="w", padx=6)
        InfoBulle(self.champ_delai, L.INFOBULLES["delai"])

        ttk.Label(zone_c, text=L.LBL_NB_CARACTERES).grid(row=4, column=0, sticky="w")
        self.lbl_nb = ttk.Label(zone_c, text="0")
        self.lbl_nb.grid(row=4, column=1, sticky="w", padx=6)

        ttk.Label(zone_c, text=L.LBL_ETAT_WORD).grid(row=5, column=0, sticky="w")
        self.lbl_word = ttk.Label(zone_c, text="")
        self.lbl_word.grid(row=5, column=1, sticky="w", padx=6)

        # Zone E : progression
        zone_e = ttk.LabelFrame(cadre, text=L.ZONE_PROGRESSION, padding=6)
        zone_e.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        zone_e.columnconfigure(0, weight=1)
        self.barre = ttk.Progressbar(zone_e, maximum=100)
        self.barre.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.lbl_saisis = ttk.Label(zone_e)
        self.lbl_saisis.grid(row=1, column=0, sticky="w")
        self.lbl_etat = ttk.Label(zone_e, font=("Segoe UI", 10, "bold"))
        self.lbl_etat.grid(row=2, column=0, sticky="w")
        self.lbl_mode_utilise = ttk.Label(zone_e)
        self.lbl_mode_utilise.grid(row=3, column=0, sticky="w")
        self.lbl_vitesse_reelle = ttk.Label(zone_e)
        self.lbl_vitesse_reelle.grid(row=4, column=0, sticky="w")
        self.lbl_message = ttk.Label(zone_e, wraplength=780, foreground="#8a1c1c", justify="left")
        self.lbl_message.grid(row=5, column=0, columnspan=2, sticky="w", pady=(4, 0))

        # Zone D : commandes
        zone_d = ttk.LabelFrame(cadre, text=L.ZONE_COMMANDES, padding=6)
        zone_d.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        self.btn_demarrer = ttk.Button(zone_d, text=L.BTN_DEMARRER, command=self.demarrer)
        self.btn_pause = ttk.Button(zone_d, text=L.BTN_PAUSE, command=self.moteur.mettre_en_pause)
        self.btn_reprendre = ttk.Button(zone_d, text=L.BTN_REPRENDRE, command=self.reprendre)
        self.btn_arreter = ttk.Button(zone_d, text=L.BTN_ARRETER, command=self.moteur.arreter)
        self.btn_effacer = ttk.Button(zone_d, text=L.BTN_EFFACER, command=self.effacer)
        self.btn_importer = ttk.Button(zone_d, text=L.BTN_IMPORTER, command=self.importer)
        self.btn_parametres = ttk.Button(zone_d, text=L.BTN_PARAMETRES, command=self.ouvrir_parametres)
        self.btn_apropos = ttk.Button(zone_d, text=L.BTN_APROPOS, command=self.apropos)
        self.btn_quitter = ttk.Button(zone_d, text=L.BTN_QUITTER, command=self.quitter)
        boutons = [self.btn_demarrer, self.btn_pause, self.btn_reprendre, self.btn_arreter,
                   self.btn_effacer, self.btn_importer, self.btn_parametres, self.btn_apropos,
                   self.btn_quitter]
        for i, bouton in enumerate(boutons):
            bouton.grid(row=i // 3, column=i % 3, sticky="ew", padx=3, pady=3)
        for c in range(3):
            zone_d.columnconfigure(c, weight=1)
        ttk.Label(zone_d, text=f"Arrêt d'urgence : {L.RACCOURCI_URGENCE}").grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(4, 0))

    # --- Actions ---

    def _texte(self) -> str:
        return self.zone_texte.get("1.0", "end-1c")

    def _sur_modification(self, _):
        self.zone_texte.edit_modified(False)
        self._maj_compteur()

    def _maj_compteur(self):
        self.lbl_nb.config(text=str(len(self._texte())))

    def _mode_interne(self) -> str:
        return MODE_HUMAIN if self.var_mode.get() == L.MODE_HUMAIN else MODE_RAPIDE

    def _sur_changement_mode(self):
        self.var_vitesse.set(VITESSE_DEFAUT[self.var_mode.get()])
        humain = self._mode_interne() == MODE_HUMAIN
        self.echelle_intensite.state(["!disabled"] if humain else ["disabled"])

    def importer(self, types=None):
        if types is None:
            types = [(L.TYPE_TOUS, "*.txt *.docx"), (L.TYPE_TXT, "*.txt"), (L.TYPE_DOCX, "*.docx")]
        chemin = filedialog.askopenfilename(title=L.TITRE_OUVRIR_FICHIER, filetypes=types)
        if not chemin:
            return
        try:
            contenu = importer_fichier(chemin)
        except ErreurImportation as exc:
            messagebox.showerror(L.TITRE_ERREUR, str(exc))
            return
        self.zone_texte.delete("1.0", "end")
        self.zone_texte.insert("1.0", contenu)
        if chemin.lower().endswith(".docx"):
            messagebox.showinfo(L.TITRE_INFO, L.MSG_LIMITE_DOCX)

    def effacer(self):
        if self._texte() and messagebox.askyesno(L.TITRE_CONFIRMATION, L.MSG_CONFIRMER_EFFACER):
            self.zone_texte.delete("1.0", "end")

    def _delai(self) -> int:
        try:
            return max(1, min(60, int(self.var_delai.get())))
        except (tk.TclError, ValueError):
            return 5

    def demarrer(self):
        texte = self._texte()
        if texte_est_vide(texte):
            messagebox.showwarning(L.TITRE_ATTENTION, L.MSG_TEXTE_VIDE)
            return
        etat = securite.etat_word()
        if etat == securite.ETAT_NON_INSTALLE:
            messagebox.showerror(L.TITRE_ERREUR, L.MSG_WORD_NON_INSTALLE)
            return
        if etat == securite.ETAT_FERME:
            messagebox.showwarning(L.TITRE_ATTENTION, L.MSG_WORD_FERME)
            return
        self.moteur.configurer(texte, self._mode_interne(), self.var_vitesse.get(),
                               self.var_intensite.get(), self.taille_groupe.get())
        self.moteur.demarrer(self._delai())

    def reprendre(self):
        self.moteur.reprendre(self._delai())

    def ouvrir_parametres(self):
        fenetre = tk.Toplevel(self.racine)
        fenetre.title(L.BTN_PARAMETRES)
        fenetre.transient(self.racine)
        fenetre.resizable(False, False)
        cadre = ttk.Frame(fenetre, padding=12)
        cadre.pack()
        ttk.Label(cadre, text=L.LBL_TAILLE_GROUPE).grid(row=0, column=0, sticky="w")
        ttk.Spinbox(cadre, from_=1, to=10, textvariable=self.taille_groupe, width=5).grid(
            row=0, column=1, padx=8)
        ttk.Checkbutton(cadre, text=L.LBL_JOURNAL, variable=self.journal_actif,
                        command=lambda: journal.activer(self.journal_actif.get())).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Button(cadre, text=L.BTN_FERMER, command=fenetre.destroy).grid(row=2, column=1, sticky="e")

    def apropos(self):
        messagebox.showinfo(L.BTN_APROPOS, L.TEXTE_APROPOS.format(
            nom=L.NOM_LOGICIEL, version=VERSION, urgence=L.RACCOURCI_URGENCE))

    def quitter(self):
        if self.moteur.en_cours():
            if not messagebox.askyesno(L.TITRE_CONFIRMATION, L.MSG_CONFIRMER_QUITTER):
                return
            self.moteur.arreter()
        self.racine.destroy()

    # --- Mise à jour périodique ---

    def _boucle_interface(self):
        m = self.moteur
        etat = m.etat
        total = m.total
        pct = (100 * m.position / total) if total else 0
        self.barre["value"] = pct
        self.lbl_saisis.config(
            text=f"{L.LBL_CARACTERES_SAISIS} : {m.position} {L.LBL_SUR} {total} ({pct:.0f} %)")
        libelle = ETAT_LIBELLE[etat]
        if etat == Etat.ATTENTE and not texte_est_vide(self._texte()):
            libelle = L.ETAT_PRET
        self.lbl_etat.config(text=f"{L.LBL_ETAT} : {libelle}")
        self.lbl_message.config(text=m.message)
        self.lbl_mode_utilise.config(
            text=f"{L.LBL_MODE_UTILISE} : "
                 f"{L.MODE_HUMAIN if m.mode == MODE_HUMAIN else L.MODE_RAPIDE}")
        reelle = m.vitesse_reelle()
        self.lbl_vitesse_reelle.config(
            text=f"{L.LBL_VITESSE_REELLE} : {reelle:.0f} {L.UNITE_CPS}" if reelle else "")
        self.lbl_vitesse.config(text=str(self.var_vitesse.get()))
        self.lbl_intensite.config(text=str(self.var_intensite.get()))

        maintenant = self.racine.tk.call("clock", "milliseconds")
        if int(maintenant) >= self.prochaine_verif_word:
            self.etat_word = securite.etat_word()
            self.lbl_word.config(text=LIBELLE_ETAT_WORD[self.etat_word])
            self.prochaine_verif_word = int(maintenant) + 500
        self._maj_boutons(etat)
        self.racine.after(100, self._boucle_interface)

    def _maj_boutons(self, etat: Etat):
        actif = etat in (Etat.COMPTE_A_REBOURS, Etat.VERIFICATION, Etat.EN_COURS)
        reprise = etat in (Etat.PAUSE, Etat.SUSPENDUE)
        inactif = not actif and not reprise

        def regler(bouton, active):
            bouton.state(["!disabled"] if active else ["disabled"])

        regler(self.btn_demarrer, inactif)
        regler(self.btn_pause, actif)
        regler(self.btn_reprendre, reprise)
        regler(self.btn_arreter, actif or reprise)
        regler(self.btn_effacer, inactif)
        regler(self.btn_importer, inactif)
        regler(self.btn_import_txt, inactif)
        regler(self.btn_import_docx, inactif)
        regler(self.btn_parametres, inactif)
        regler(self.liste_mode, inactif)
        regler(self.champ_delai, not actif)
        self.zone_texte.config(state="normal" if inactif else "disabled")


def lancer():
    racine = tk.Tk()
    moteur = MoteurSaisie(securite.obtenir_fenetre_active, _envoyeur_windows())
    Application(racine, moteur)
    if sys.platform == "win32":
        SurveillanceUrgence(moteur).start()
    racine.mainloop()


def _envoyeur_windows():
    if sys.platform == "win32":
        from . import winapi
        return winapi.envoyer_texte

    def indisponible(_):
        raise OSError("Windows requis")
    return indisponible
