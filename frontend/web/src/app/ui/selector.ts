import { CdkConnectedOverlay, CdkOverlayOrigin, ConnectedPosition } from '@angular/cdk/overlay';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  forwardRef,
  input,
  model,
  output,
  signal,
} from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

export interface Opcion<T = string> {
  valor: T;
  etiqueta: string;
  /** Clase extra para colorear la opción (p. ej. el rol). */
  clase?: string;
}

let siguienteId = 0;

/**
 * Desplegable con el estilo de la web, en lugar del <select> nativo.
 * Patrón ARIA «combobox + listbox»: el foco se queda en el botón y la opción activa se anuncia
 * con aria-activedescendant. Teclado: flechas, Inicio/Fin, Enter/Espacio, Escape y letras.
 * La lista se pinta en un overlay del CDK, fuera de los paneles de cristal: dentro de un
 * elemento con backdrop-filter quedaría recortada.
 */
@Component({
  selector: 'app-selector',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [CdkOverlayOrigin, CdkConnectedOverlay],
  providers: [{ provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => Selector), multi: true }],
  host: { '[class.compacto]': 'compacto()', '[class.pildora]': 'pildora()' },
  template: `
    <button
      type="button"
      class="disparador"
      cdkOverlayOrigin
      #origen="cdkOverlayOrigin"
      role="combobox"
      aria-haspopup="listbox"
      [id]="idCampo()"
      [class]="seleccionada()?.clase ?? ''"
      [class.abierto]="abierto()"
      [class.invalido]="invalido()"
      [attr.aria-expanded]="abierto()"
      [attr.aria-controls]="idLista"
      [attr.aria-activedescendant]="abierto() && activo() >= 0 ? idLista + '-' + activo() : null"
      [attr.aria-label]="etiquetaAria()"
      [disabled]="deshabilitado() || bloqueado()"
      (click)="alternar(origen)"
      (keydown)="tecla($event, origen)"
      (blur)="alTocar()"
    >
      <span class="texto" [class.vacio]="!seleccionada()">{{ seleccionada()?.etiqueta ?? marcador() }}</span>
      <svg aria-hidden="true" class="flecha" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6" /></svg>
    </button>

    <ng-template
      cdkConnectedOverlay
      [cdkConnectedOverlayOrigin]="origen"
      [cdkConnectedOverlayOpen]="abierto()"
      [cdkConnectedOverlayPositions]="posiciones"
      [cdkConnectedOverlayMinWidth]="ancho()"
      (overlayOutsideClick)="cerrar()"
      (detach)="cerrar()"
    >
      <ul class="lista" role="listbox" [id]="idLista" [attr.aria-label]="etiquetaAria()">
        @for (o of opciones(); track o.valor; let i = $index) {
          <li
            role="option"
            [id]="idLista + '-' + i"
            [class]="o.clase ?? ''"
            [class.activa]="i === activo()"
            [class.elegida]="o.valor === valor()"
            [attr.aria-selected]="o.valor === valor()"
            (mousedown)="$event.preventDefault()"
            (mouseenter)="activo.set(i)"
            (click)="elegir(o)"
          >
            <span>{{ o.etiqueta }}</span>
            @if (o.valor === valor()) {
              <svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7" /></svg>
            }
          </li>
        }
      </ul>
    </ng-template>
  `,
  styles: `
    :host { display: block; min-width: 0; }
    .disparador {
      width: 100%; min-height: 52px; display: flex; align-items: center; justify-content: space-between; gap: 10px;
      padding: 0 14px 0 16px; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 14px;
      background: rgba(0, 0, 0, 0.35); color: var(--texto); font-family: inherit; font-size: 15px; text-align: left;
      cursor: pointer; transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
    }
    .disparador:hover:not(:disabled) { background: rgba(0, 0, 0, 0.45); border-color: rgba(255, 255, 255, 0.14); }
    .disparador:focus-visible, .disparador.abierto {
      outline: none; border-color: rgba(255, 59, 78, 0.7);
      box-shadow: 0 0 0 4px rgba(224, 30, 60, 0.18), 0 0 24px rgba(224, 30, 60, 0.25);
    }
    .disparador.invalido { border-color: rgba(255, 59, 78, 0.7); }
    .disparador:disabled { cursor: not-allowed; opacity: 0.6; }
    .texto { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .texto.vacio { color: var(--tenue); }
    .flecha { flex: none; color: var(--apagado); transition: transform 0.2s; }
    .abierto .flecha { transform: rotate(180deg); color: var(--sangre-claro); }

    :host(.compacto) .disparador { min-height: 44px; border-radius: 12px; font-size: 14px; padding: 0 12px 0 14px; }

    /* Variante píldora (rol en la tabla de usuarios) */
    :host(.pildora) { display: inline-block; }
    :host(.pildora) .disparador {
      min-height: 38px; width: auto; min-width: 128px; gap: 8px; padding: 0 12px 0 14px; border: 0; border-radius: 999px;
      font-weight: 700; font-size: 13px;
    }
    :host(.pildora) .flecha { color: currentColor; opacity: 0.7; }

    .lista {
      margin: 6px 0; padding: 6px; list-style: none; max-height: 300px; overflow-y: auto; border-radius: 16px;
      background: linear-gradient(170deg, rgba(36, 22, 30, 0.96), rgba(16, 10, 14, 0.97));
      backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1), 0 24px 60px -16px rgba(0, 0, 0, 0.95), 0 0 0 1px rgba(255, 255, 255, 0.04);
      font-family: var(--sans); font-size: 14px; color: var(--texto-2);
    }
    li {
      min-height: 40px; display: flex; align-items: center; justify-content: space-between; gap: 12px;
      padding: 0 12px; border-radius: 10px; cursor: pointer; transition: background 0.15s, color 0.15s;
    }
    li.activa { background: rgba(224, 30, 60, 0.16); color: #fff4f1; }
    li.elegida { color: var(--oro-claro); font-weight: 600; }
    li.elegida svg { color: var(--sangre-claro); }

    /* Colores por valor (roles y severidades) */
    .rol-usuario { color: #f1e6e0; } .rol-analista { color: #f0c987; } .rol-admin { color: #ff7a88; }
    .disparador.rol-usuario { background: rgba(241, 230, 224, 0.09); }
    .disparador.rol-analista { background: rgba(212, 175, 110, 0.16); }
    .disparador.rol-admin { background: rgba(224, 30, 60, 0.18); }
    /* Acciones de auditoría */
    li.alerta { color: #ff4d5e; } li.privilegio { color: #f0c987; }
  `,
})
export class Selector<T = string> implements ControlValueAccessor {
  readonly opciones = input.required<Opcion<T>[]>();
  readonly marcador = input('Elige una opción');
  readonly idCampo = input<string>(`selector-${siguienteId++}`);
  readonly etiquetaAria = input<string | null>(null);
  readonly compacto = input(false);
  readonly pildora = input(false);
  readonly invalido = input(false);
  /** Deshabilitado sin formulario (p. ej. el rol de tu propia cuenta). */
  readonly bloqueado = input(false);
  /** Uso sin formulario: [(valor)] y (cambio). */
  readonly valor = model<T | null>(null);
  readonly cambio = output<T>();

  protected readonly idLista = `${this.idCampo()}-lista-${siguienteId++}`;
  protected readonly abierto = signal(false);
  protected readonly activo = signal(-1);
  protected readonly ancho = signal(0);
  protected readonly deshabilitado = signal(false);
  protected readonly seleccionada = computed(() => this.opciones().find((o) => o.valor === this.valor()));

  protected readonly posiciones: ConnectedPosition[] = [
    { originX: 'start', originY: 'bottom', overlayX: 'start', overlayY: 'top' },
    { originX: 'start', originY: 'top', overlayX: 'start', overlayY: 'bottom' },
  ];

  private alCambiar: (v: T | null) => void = () => undefined;
  protected alTocar: () => void = () => undefined;

  // --- ControlValueAccessor ---
  writeValue(v: T | null): void {
    this.valor.set(v);
  }
  registerOnChange(fn: (v: T | null) => void): void {
    this.alCambiar = fn;
  }
  registerOnTouched(fn: () => void): void {
    this.alTocar = fn;
  }
  setDisabledState(deshabilitado: boolean): void {
    this.deshabilitado.set(deshabilitado);
  }

  protected alternar(origen: CdkOverlayOrigin): void {
    if (this.abierto()) this.cerrar();
    else this.abrir(origen);
  }

  private abrir(origen: CdkOverlayOrigin): void {
    if (this.deshabilitado() || this.bloqueado()) return;
    this.ancho.set((origen.elementRef.nativeElement as HTMLElement).getBoundingClientRect().width);
    const actual = this.opciones().findIndex((o) => o.valor === this.valor());
    this.activo.set(actual >= 0 ? actual : 0);
    this.abierto.set(true);
  }

  protected cerrar(): void {
    this.abierto.set(false);
  }

  protected elegir(o: Opcion<T>): void {
    this.cerrar();
    if (o.valor === this.valor()) return;
    this.valor.set(o.valor);
    this.alCambiar(o.valor);
    this.cambio.emit(o.valor);
  }

  protected tecla(e: KeyboardEvent, origen: CdkOverlayOrigin): void {
    const n = this.opciones().length;
    if (!this.abierto()) {
      if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) {
        e.preventDefault();
        this.abrir(origen);
      }
      return;
    }
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        this.activo.update((i) => Math.min(n - 1, i + 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        this.activo.update((i) => Math.max(0, i - 1));
        break;
      case 'Home':
        e.preventDefault();
        this.activo.set(0);
        break;
      case 'End':
        e.preventDefault();
        this.activo.set(n - 1);
        break;
      case 'Enter':
      case ' ':
        e.preventDefault();
        if (this.activo() >= 0) this.elegir(this.opciones()[this.activo()]);
        break;
      case 'Escape':
        e.preventDefault();
        this.cerrar();
        break;
      case 'Tab':
        this.cerrar();
        break;
      default:
        // Salto por letra: primera opción que empieza por la tecla pulsada
        if (e.key.length === 1) {
          const i = this.opciones().findIndex((o) => o.etiqueta.toLowerCase().startsWith(e.key.toLowerCase()));
          if (i >= 0) this.activo.set(i);
        }
    }
  }
}
