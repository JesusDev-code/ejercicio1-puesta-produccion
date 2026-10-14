import { AbstractControl, ValidationErrors, ValidatorFn } from '@angular/forms';

export const MINIMO_CONTRASENA = 12;

/** Validador de grupo: los dos campos indicados tienen que coincidir. */
export function coinciden(a: string, b: string): ValidatorFn {
  return (grupo: AbstractControl): ValidationErrors | null => {
    const va = grupo.get(a)?.value;
    const vb = grupo.get(b)?.value;
    return va && vb && va !== vb ? { noCoinciden: true } : null;
  };
}

/**
 * Contraseña aleatoria con el generador criptográfico del navegador (no Math.random).
 * Sin caracteres que se confunden al dictarla (0/O, 1/l/I).
 */
export function generarContrasena(longitud = 20): string {
  const alfabeto = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789-_.';
  // Se descartan los bytes del final del rango para que todos los caracteres sean equiprobables
  const limite = 256 - (256 % alfabeto.length);
  let resultado = '';
  while (resultado.length < longitud) {
    for (const byte of crypto.getRandomValues(new Uint8Array(longitud * 2))) {
      if (byte < limite && resultado.length < longitud) resultado += alfabeto[byte % alfabeto.length];
    }
  }
  return resultado;
}
