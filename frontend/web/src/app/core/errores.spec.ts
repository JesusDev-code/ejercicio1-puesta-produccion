import { HttpErrorResponse } from '@angular/common/http';

import { camposInvalidos, codigo, deFirebase, detalle, mensajeGeneral } from './errores';

const http = (status: number, error: unknown = null) => new HttpErrorResponse({ status, error });

describe('errores', () => {
  describe('codigo', () => {
    it('devuelve el status de un error HTTP', () => {
      expect(codigo(http(404))).toBe(404);
    });

    it('trata cualquier otra cosa como «sin conexión» (0)', () => {
      expect(codigo(new Error('red'))).toBe(0);
      expect(codigo(undefined)).toBe(0);
    });
  });

  describe('detalle', () => {
    it('extrae el detail de texto de la API', () => {
      expect(detalle(http(409, { detail: 'Ya existe' }))).toBe('Ya existe');
    });

    it('ignora un detail que no es texto (los 422 de FastAPI son listas)', () => {
      expect(detalle(http(422, { detail: [{ loc: ['body', 'x'] }] }))).toBeNull();
    });
  });

  describe('camposInvalidos', () => {
    it('recoge los campos señalados por un 422', () => {
      const error = http(422, {
        detail: [{ loc: ['body', 'titulo'] }, { loc: ['body', 'descripcion'] }],
      });
      expect([...camposInvalidos(error)]).toEqual(['titulo', 'descripcion']);
    });

    it('no inventa campos con otros códigos', () => {
      expect(camposInvalidos(http(400, { detail: [{ loc: ['body', 'x'] }] })).size).toBe(0);
    });
  });

  describe('mensajeGeneral', () => {
    it.each([
      [0, 'No hay conexión con la API.'],
      [403, 'No tienes permiso para esta acción.'],
      [404, 'No existe.'],
      [429, 'Demasiadas peticiones. Espera un minuto antes de volver a probar.'],
      [503, 'Algo ha fallado en el servidor.'],
    ])('código %i → «%s»', (status, texto) => {
      expect(mensajeGeneral(status === 0 ? new Error() : http(status))).toBe(texto);
    });

    it('en un 409 usa el motivo que da la API', () => {
      expect(mensajeGeneral(http(409, { detail: 'Transición no permitida' }))).toBe('Transición no permitida');
    });

    it('nunca muestra trazas internas de un 500', () => {
      expect(mensajeGeneral(http(500, { detail: 'Traceback (most recent call last)…' }))).toBe(
        'Algo ha fallado en el servidor.',
      );
    });
  });

  describe('deFirebase', () => {
    it.each([
      ['auth/invalid-credential', 401],
      ['auth/wrong-password', 401],
      ['auth/user-not-found', 401],
      ['auth/too-many-requests', 429],
      ['auth/network-request-failed', 0],
      ['auth/otra-cosa', 400],
    ])('%s → %i', (code, status) => {
      expect(deFirebase({ code }).status).toBe(status);
    });

    it('una cuenta deshabilitada se ve igual que una contraseña mala (sin enumeración)', () => {
      expect(deFirebase({ code: 'auth/user-disabled' }).status).toBe(
        deFirebase({ code: 'auth/wrong-password' }).status,
      );
    });

    it('aguanta errores sin código', () => {
      expect(deFirebase(null).status).toBe(400);
    });
  });
});
