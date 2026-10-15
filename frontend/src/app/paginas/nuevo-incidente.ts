import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { Api } from '../core/api';
import { camposInvalidos, codigo, mensajeGeneral } from '../core/errores';
import { CATEGORIAS, Categoria, SEVERIDADES, Severidad, entradas } from '../core/modelos';
import { Opcion, Selector } from '../ui/selector';

const NOMBRES_CAMPO: Record<string, string> = {
  titulo: 'el título',
  severidad: 'la severidad',
  categoria: 'la categoría',
  descripcion: 'la descripción',
};

@Component({
  selector: 'app-nuevo-incidente',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [ReactiveFormsModule, RouterLink, Selector],
  template: `
    <div class="pila">
      <header class="textos">
        <a routerLink="/incidentes" class="volver">← Volver al listado</a>
        <span class="ruta">~/incidentes/nuevo</span>
        <h1 class="titulo">Reportar incidencia</h1>
        <p class="subtitulo">Describe qué ha pasado con el mayor detalle posible. Podrás editarlo mientras siga abierto.</p>
      </header>

      @if (resumenErrores()) {
        <div role="alert" class="aviso aviso-error ancho-form">
          <span class="codigo">422</span><span>{{ resumenErrores() }}</span>
        </div>
      } @else if (errorGeneral()) {
        <div role="alert" class="aviso aviso-error ancho-form">
          <span class="codigo">{{ errorGeneral()!.codigo || 'red' }}</span><span>{{ errorGeneral()!.mensaje }}</span>
        </div>
      }

      <form aria-label="Nueva incidencia" class="cristal formulario ancho-form" [formGroup]="form" (ngSubmit)="enviar()" novalidate>
        <div class="campo">
          <div class="campo-cabecera">
            <label for="n-titulo">Título</label>
            <span class="contador">{{ titulo().length }}/120</span>
          </div>
          <input id="n-titulo" type="text" class="entrada" maxlength="120" formControlName="titulo"
            [class.invalida]="invalido('titulo')" aria-describedby="n-titulo-err" [attr.aria-invalid]="invalido('titulo')" />
          @if (invalido('titulo')) { <span id="n-titulo-err" class="error-campo">Entre 3 y 120 caracteres.</span> }
        </div>

        <fieldset class="severidades-grupo">
          <legend class="etiqueta" [class.leyenda-error]="invalido('severidad')">
            Severidad{{ invalido('severidad') ? ' · obligatoria' : '' }}
          </legend>
          <div class="severidades">
            @for (s of severidades; track s[0]) {
              <label class="sev" [class.marcada]="severidad() === s[0]" [class.con-error]="invalido('severidad')" [class]="s[1].clase">
                <span class="sev-cabecera">
                  <span class="sev-nombre"><span aria-hidden="true" class="punto"></span>{{ s[1].nombre }}</span>
                  <input type="radio" formControlName="severidad" [value]="s[0]" />
                </span>
                <span class="sev-ayuda">{{ s[1].ayuda }}</span>
              </label>
            }
          </div>
        </fieldset>

        <div class="campo">
          <label for="n-cat">Categoría</label>
          <app-selector idCampo="n-cat" class="selector" [opciones]="categorias" formControlName="categoria" [invalido]="invalido('categoria')" />
        </div>

        <div class="campo">
          <div class="campo-cabecera">
            <label for="n-desc">Descripción</label>
            <span class="contador">{{ descripcion().length }}/5000 · texto plano</span>
          </div>
          <textarea id="n-desc" rows="8" class="entrada" maxlength="5000" formControlName="descripcion"
            [class.invalida]="invalido('descripcion')" aria-describedby="n-desc-err" [attr.aria-invalid]="invalido('descripcion')"></textarea>
          @if (invalido('descripcion')) { <span id="n-desc-err" class="error-campo">La descripción es obligatoria.</span> }
        </div>

        <div class="acciones">
          <button type="submit" class="btn btn-sangre" [disabled]="enviando()">
            {{ enviando() ? 'Enviando…' : 'Enviar reporte' }} <span aria-hidden="true">→</span>
          </button>
          <a routerLink="/incidentes" class="btn btn-suave grande">Cancelar</a>
        </div>
      </form>
    </div>
  `,
  styles: `
    .pila { display: flex; flex-direction: column; gap: 28px; }
    .textos { display: flex; flex-direction: column; gap: 10px; }
    .volver { align-self: flex-start; font-size: 13px; color: var(--apagado); text-decoration: none; }
    .volver:hover { color: var(--texto); }
    .ancho-form { max-width: 880px; }
    .formulario { padding: 36px; border-radius: 24px; display: flex; flex-direction: column; gap: 28px; }
    .severidades-grupo { margin: 0; padding: 0; border: 0; display: flex; flex-direction: column; gap: 12px; }
    legend { padding: 0 0 12px; }
    .leyenda-error { color: var(--sangre-rosa); }
    .severidades { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
    .sev {
      position: relative; min-width: 0; min-height: 104px; display: flex; flex-direction: column; justify-content: space-between;
      gap: 10px; padding: 16px; border-radius: 16px; cursor: pointer; transition: background 0.2s, box-shadow 0.2s;
      background: rgba(255, 255, 255, 0.04); box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
    }
    .sev:hover { background: rgba(255, 255, 255, 0.07); }
    .sev.con-error { box-shadow: inset 0 0 0 1px rgba(255, 59, 78, 0.4); }
    .sev.marcada {
      background: linear-gradient(160deg, rgba(224, 30, 60, 0.22), rgba(224, 30, 60, 0.05));
      box-shadow: inset 0 0 0 1px rgba(255, 90, 110, 0.55), 0 0 30px -6px rgba(224, 30, 60, 0.6);
    }
    .sev:focus-within { outline: 2px solid #ff3b4e; outline-offset: 3px; }
    .sev-baja { --sev: #b8a5ab; } .sev-media { --sev: #f0c987; } .sev-alta { --sev: #ff9a5c; } .sev-critica { --sev: #ff4d5e; }
    .sev-cabecera { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
    .sev-nombre { display: inline-flex; align-items: center; gap: 8px; font-size: 14px; font-weight: 700; color: var(--sev); }
    .sev input { accent-color: var(--sangre); width: 18px; height: 18px; margin: 0; }
    .sev-ayuda { font-size: 12px; line-height: 1.45; color: var(--apagado); }
    .selector { max-width: 420px; }
    .acciones { display: flex; flex-wrap: wrap; gap: 12px; padding-top: 4px; }
    .grande { min-height: 50px; border-radius: 14px; padding: 0 22px; color: var(--texto-2); }
    @media (max-width: 720px) { .formulario { padding: 22px; } }
  `,
})
export class NuevoIncidente {
  private readonly api = inject(Api);
  private readonly router = inject(Router);

  protected readonly severidades = entradas(SEVERIDADES);
  protected readonly categorias: Opcion<Categoria>[] = entradas(CATEGORIAS).map(([valor, etiqueta]) => ({ valor, etiqueta }));

  protected readonly form = inject(FormBuilder).nonNullable.group({
    titulo: ['', [Validators.required, Validators.minLength(3), Validators.maxLength(120)]],
    severidad: ['' as Severidad | '', Validators.required],
    categoria: ['phishing' as Categoria, Validators.required],
    descripcion: ['', [Validators.required, Validators.maxLength(5000)]],
  });

  protected readonly titulo = toSignal(this.form.controls.titulo.valueChanges, { initialValue: '' });
  protected readonly descripcion = toSignal(this.form.controls.descripcion.valueChanges, { initialValue: '' });
  protected readonly severidad = toSignal(this.form.controls.severidad.valueChanges, { initialValue: '' });

  protected readonly enviando = signal(false);
  /** Campos marcados: por la validación local al enviar o por un 422 de la API. */
  protected readonly erroneos = signal<Set<string>>(new Set());
  protected readonly errorGeneral = signal<{ codigo: number; mensaje: string } | null>(null);

  protected readonly resumenErrores = computed(() => {
    const campos = [...this.erroneos()].map((c) => NOMBRES_CAMPO[c]).filter(Boolean);
    if (!campos.length) return '';
    const lista = campos.length === 1 ? campos[0] : `${campos.slice(0, -1).join(', ')} y ${campos.at(-1)}`;
    return campos.length === 1 ? `Hay 1 campo por revisar: ${lista}.` : `Hay ${campos.length} campos por revisar: ${lista}.`;
  });

  protected invalido(campo: string): boolean {
    return this.erroneos().has(campo);
  }

  async enviar(): Promise<void> {
    this.errorGeneral.set(null);
    const locales = Object.entries(this.form.controls)
      .filter(([, control]) => control.invalid)
      .map(([nombre]) => nombre);
    this.erroneos.set(new Set(locales));
    if (locales.length) return;

    this.enviando.set(true);
    try {
      const { severidad, ...resto } = this.form.getRawValue();
      const creado = await this.api.crearIncidente({ ...resto, severidad: severidad as Severidad });
      await this.router.navigate(['/incidentes', creado.id]);
    } catch (e) {
      const campos = camposInvalidos(e);
      this.erroneos.set(campos);
      if (!campos.size) this.errorGeneral.set({ codigo: codigo(e), mensaje: mensajeGeneral(e) });
    } finally {
      this.enviando.set(false);
    }
  }
}
