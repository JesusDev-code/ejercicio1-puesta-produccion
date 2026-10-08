class ErrorDominio(Exception):
    codigo = 400

    def __init__(self, detalle: str):
        super().__init__(detalle)
        self.detalle = detalle


class NoAutenticado(ErrorDominio):
    codigo = 401


class Prohibido(ErrorDominio):
    codigo = 403


class NoEncontrado(ErrorDominio):
    codigo = 404


class Conflicto(ErrorDominio):
    codigo = 409


class Invalido(ErrorDominio):
    codigo = 422
