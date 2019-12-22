# coding=utf-8
import json
import logging
import re
from bs4 import BeautifulSoup

import requests

from mareabot.model import Previsione, DBIstance
from mareabot.social import telegram_api

logger = logging.getLogger("MareaBot")

MAREA_API_URL = (
    "http://dati.venezia.it/sites/default/files/dataset/opendata/previsione.json"
)
MAREA_ISTANTANEA_API = "https://www.comune.venezia.it/it/content/centro-previsioni-e-segnalazioni-maree-beta"

VENTO_ISTANTANEO_API = "https://www.comune.venezia.it/sites/default/files/publicCPSM2/stazioni/trimestrale/Stazione_DigaSudLido.html"


def get_vento() -> (float, float):
    get_url = requests.get(VENTO_ISTANTANEO_API)
    html_data = get_url.text

    bs = BeautifulSoup(html_data, "html.parser")

    vv_last = vvmax_last = None
    for row in bs.findAll("tr"):
        aux = row.findAll("td")
        if len(aux) == 6:
            gg, ora, liv, vv, vv_max, dv = aux
            if vv.text != "":
                vv_last = vv
                vvmax_last = vv_max
            else:
                return float(vv_last.text) * 3.6, float(vvmax_last.text) * 3.6
    return (0.0, 0.0)


def get_istantanea_marea() -> int:
    get_url = requests.get(MAREA_ISTANTANEA_API)
    get_text = get_url.text
    soup = BeautifulSoup(get_text, "html.parser")
    try:
        company = soup.findAll("b", class_="text-marea-line5")[0].text
    except IndexError:
        try:
            company = soup.findAll("b", class_="text-marea-line4")[0].text
        except IndexError:
            try:
                company = soup.findAll("b", class_="text-marea-line3")[0].text
            except IndexError:
                try:
                    company = soup.findAll("b", class_="text-marea-line2")[0].text
                except IndexError:
                    try:
                        company = soup.findAll("b", class_="text-marea-line1")[0].text
                    except IndexError:
                        company = "+ 0cm"
    company = company.strip()
    try:
        number = int(company.split("cm")[0].split("+")[1])
    except IndexError:
        number = int(company.split("cm")[0].split("-")[1])
    return number


def posting_instant(db_istance: DBIstance, maximum: int = 110):
    estended = ""
    hight = get_istantanea_marea()
    vento, vento_max = get_vento()
    db_dato = db_istance.instante

    if db_dato is None:
        db_dato = 0
    if int(hight) == int(db_dato):
        return
    else:
        db_istance.instante = hight

    if int(maximum) <= int(hight):
        estended = "Ultima misurazione è cm " + str(hight)
        estended += (
            "\nIl vento è "
            + str(vento)
            + " km/h e al massimo il vento è "
            + str(vento_max)
            + " km/h"
        )
    try:
        if db_istance.message_hight is not None:
            telegram_api.telegram_channel_delete_message(db_istance.message_hight)
    except Exception as e:
        logger.error(e)

    try:
        if estended != "":
            message = telegram_api.telegram_channel_send(estended)
            db_istance.message_hight = message.message_id
    except Exception as e:
        logger.error(e)


def reading_api():
    datas = json.loads(requests.get(MAREA_API_URL).text)
    db_istance = DBIstance()
    if db_istance.last != datas[0]["DATA_PREVISIONE"]:
        adding_data(datas, db_istance)
    if int(get_istantanea_marea()) >= 110:
        posting_instant(db_istance)
    else:
        if db_istance.message_hight is not None:
            telegram_api.telegram_channel_delete_message(db_istance.message_hight)


def posting(maximum: int, db_istance: DBIstance, hight: int = 94):
    estended = ""
    if int(maximum) >= hight:
        for s in db_istance.prevision:
            estended += s.long_string(hight)
    try:
        if db_istance.message is not None:
            telegram_api.telegram_channel_delete_message(db_istance.message)
    except Exception as e:
        logger.error(e)

    try:
        if estended != "":
            message = telegram_api.telegram_channel_send(estended)
            db_istance.message = message.message_id
    except Exception as e:
        logger.error(e)


def adding_data(input_dict: dict, db_istance: DBIstance):
    maximum = -400
    for data in input_dict:
        d = Previsione(
            data["DATA_PREVISIONE"],
            data["DATA_ESTREMALE"],
            data["TIPO_ESTREMALE"],
            data["VALORE"],
        )
        maximum = max(int(maximum), int(data["VALORE"]))
        db_istance.prevision.append(d)
        db_istance.last = input_dict[0]["DATA_PREVISIONE"]
    posting(maximum=maximum, db_istance=db_istance)
