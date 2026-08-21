from enum import StrEnum


class PowerFactoryClass(StrEnum):
    """PowerFactory object classes used by the Phase 7 canonical mapper."""

    NETWORK = "ElmNet"
    SUBSTATION = "ElmSubstat"
    TERMINAL = "ElmTerm"
    CUBICLE = "StaCubic"
    CUBICLE_SWITCH = "StaSwitch"
    LINE = "ElmLne"
    LINE_TYPE = "TypLne"
    TRANSFORMER = "ElmTr2"
    TRANSFORMER_TYPE = "TypTr2"
    SWITCH = "ElmCoup"
    LOAD = "ElmLod"
    GENERATOR = "ElmGenstat"
    EXTERNAL_GRID = "ElmXnet"
    FEEDER = "ElmFeeder"
    GRAPHIC_NET = "IntGrfnet"
    GRAPHIC = "IntGrf"
    GRAPHIC_CON = "IntGrfcon"
