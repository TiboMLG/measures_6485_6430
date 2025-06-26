# ------ mesure_6485.py ------
# Par Thibault Malagarie-Cazenave
# Le 19/06/25
# ----------------------------

import pyvisa
import time
import csv
import matplotlib.pyplot as plt
import numpy as np
import math
import sys

# ---------------------------
#
# PARAMETRES
#
# ---------------------------

U = 42  # Différentiel de potentiel appliqué

e = 0.93e-3  # Épaisseur de l'échantillon
D = 5.00e-3  # Diamètre de l'électrode gardée
g = 1.30e-4  # Gap entre l'électrode de garde et l'électrode gardée

S = math.pi * (g + D) ** 2 / 4  # Surface effective de l'électrode gardée

# Variables globales
time_list = []
current_list = []
file_name = ""
inst = None
gene = None
rm = None


# ----------------------------
#
# FONCTIONS
#
# ----------------------------


# Gestionnaire pour sauvegarde et affichage des données
def save_data_and_plot():
    global time_list, current_list, file_name

    print(f"Enregistrement de {len(time_list)} points de mesure...")

    # Calculs
    current_list = inverse_6430_measures(current_list)
    current_avg_list = moving_average(current_list, 50)
    resistance_list = []
    resistivity_list = []

    for i in range(len(time_list)):
        res = U / current_avg_list[i] if current_avg_list[i] != 0 else float('inf')
        resistance_list.append(res)
        resistivity_list.append(res * S / e)

    # Écriture des données
    try:
        with open(file_name + '_all' + '.csv', 'w', newline='') as csvfile:
            csvfile.write(
                'temps(s), courant_brut(A), courant_filtre(A), resistance(Ohm), resistivite(Ohm.m)\n')  # Écriture des en-têtes
            for i in range(len(time_list)):
                csvfile.write(
                    f"{time_list[i]},{current_list[i]},{current_avg_list[i]},{resistance_list[i]},{resistivity_list[i]}\n")
        print(f"Données sauvegardées dans {file_name}_all.csv")
    except Exception as error:
        print(f"Erreur lors de la sauvegarde : {error}")

    # Affichage des données
    try:

        # Trace de I(t)
        fig_cur_neg = plt.subplot(2, 2, 1)
        fig_cur_neg.plot(time_list, current_list, label='Valeurs brutes inversées')
        fig_cur_neg.set_title("Evolution du courant de fuite en fonction du temps")
        fig_cur_neg.set_xlabel("Temps (s)")
        fig_cur_neg.set_ylabel("Courant (A)")

        fig_cur_neg = plt.subplot(2, 2, 1)
        fig_cur_neg.plot(time_list, current_avg_list, label='Valeurs filtrées inversées')
        fig_cur_neg.set_title("Evolution du courant de fuite en fonction du temps")
        fig_cur_neg.set_xlabel("Temps (s)")
        fig_cur_neg.set_ylabel("Courant (A)")
        fig_cur_neg.grid()
        fig_cur_neg.legend()

        # Trace de R(t)
        fig_res = plt.subplot(2, 2, 2)
        fig_res.plot(time_list, resistance_list, color='black', label='Résistance')
        fig_res.plot("Evolution de la résistance de l'échantillon")
        fig_res.set_xlabel("Temps (s)")
        fig_res.set_ylabel("Résistance (Ohm)")
        fig_res.grid()

        # Trace de Rho(t)
        fig_rho = plt.subplot(2, 2, 3)
        fig_rho.plot(time_list, resistivity_list, color='black', label='Résistivité')
        fig_rho.plot("Evolution de la résistivité de l'échantillon")
        fig_rho.set_xlabel("Temps (s)")
        fig_rho.set_ylabel("Résistivité (Ohm.m)")
        fig_rho.grid()

        plt.show()

    except Exception as error:
        print(f"Erreur lors de l'affichage : {error}")


# Gestionnaire de la fermeture de la communication GPIB
def cleanup_instruments():
    global rm, gene, inst

    try:
        if gene:
            print("Arrêt du générateur")
            gene.write('*RST')
            gene.close()
    except Exception as error:
        print(f"Erreur lors de l'arrêt du générateur : {error}")

    try:
        if inst:
            print("Arrêt du pico-ampèremètre")
            inst.write('*RST')
            inst.close()
    except Exception as error:
        print(f"Erreur lors de l'arrêt du femto-ampèremètre : {error}")

    try:
        if rm:
            print("Arrêt de la communication")
            rm.close()
    except Exception as error:
        print(f"Erreur lors de l'arrêt de la communication : {error}")


# Gestionnaire du signal d'arrêt
def signal_handler():
    print("/!\ \n Interruption détectée (Ctrl + C)\n/!\ ")
    print('Sauvegarde des données')
    print('Arrêt du programme')
    sys.exit(0)


def moving_average(data, neighbor):
    N = len(data)
    result = [0.0] * N

    for i in range(N):
        total = data[i]
        count = 1

        # points à gauche
        for n in range(1, neighbor + 1):
            if i - n >= 0:
                total += data[i - n]
                count += 1

        # points à droite
        for n in range(1, neighbor + 1):
            if i + n < N:
                total += data[i + n]
                count += 1

        result[i] = total / count

    return result


def avg_offset(data, time, delay):
    sum = 0
    i = 0
    t = 0
    data_offset = []

    while time[i] <= delay:
        sum += data[i]
        i += 1

    avg = sum / i

    for elem in data:
        data_offset.append(elem - avg)

    return data_offset


def inverse_6430_measures(data):
    temp = []

    for i in range(len(data)):
        temp.append(-data[i])

    return temp

# ------------------------
#
# INITIALISATION
#
# ------------------------

# Entrée du nom de fichier sortant
file_name = input('Nom du fichier csv de sortie')

# Initialisation du gestionnaire de ressources VISA
rm = pyvisa.ResourceManager()
print("Pilotes VISA disponibles :", rm.list_resources())

# Ouverture de la communication aux instruments
try:
    addr_pico = 'GPIB0::14::INSTR'
    inst = rm.open_resource(addr_pico)

    addr_gene = 'GPIB0::05::INSTR'
    gene = rm.open_resource(addr_gene)

    # Configuration basique
    inst.timeout = 5000  # timeout en ms
    inst.write_termination = '\n'  # terminaison SCPI
    inst.read_termination = '\n'

    # Vérification de l'identité
    idn = inst.query('*IDN?')
    print("Connecté à:", idn.strip())

    idn = gene.query('*IDN?')
    print("Connecté à:", idn.strip())

    # Configuration de la mesure
    inst.write('*RST')
    inst.write('CONF:CURR')
    inst.write('SENS:CURR:RANG:AUTO ON')
    # inst.write('SENS:CURR:RANG 100E-12')   # Echelle manuelle

    inst.write('SENS:CURR:NPLC 1')
    inst.write('SENS:MED ON')
    inst.write('SENS:MED:RANK 1')

    inst.write('AVER OFF')
    inst.write('SYST:AZER ON')

    # Ne renvoyer que le courant
    inst.write('FORM:ELEM CURR')

    # Configuration du générateur

    gene.write('*RST')
    gene.write('OUTP OFF')
    gene.write('APPL P25V, 25.0, 1.0')
    gene.write('APPL N25V, -17.0, 1.0')

except Exception as error:
    print(f"Erreur lors de l'ouverture de la communication aux instruments : {error}.")
    sys.exit(1)

# -----------------------------
#
# MESURES
#
# -----------------------------

# Paramètres
duree = 3.2 * 60  # durée en secondes
t0 = time.time()
i = 1
elapsed = 0
gene_state = 0

# Boucle
print(f"Démarrage des mesures pour {duree / 60:.0f} minutes…")
print("Pour arrêter la boucle et sauvegarder les données, appuyer sur Ctrl+C")

try:
    while elapsed <= duree:
        elapsed = time.time() - t0

        if elapsed >= 10 and gene_state == 0:
            gene.write('OUTP ON')

            gene_state = 1

        current = float(inst.query('read?'))

        time_list.append(elapsed)
        current_list.append(current)
        print(f"[{i:03d}] +{elapsed:.1f}s → {current:.3e} A")

        i += 1

    print("Mesures terminées")

except KeyboardInterrupt:
    print("\nInterruption détectée. Sauvegarde des données...")
    signal_handler()

except Exception as error:
    print(f"Erreur lors des mesures à t={elapsed}: {error}")

finally:
    cleanup_instruments()

    save_data_and_plot()

    print("Programme terminé")
