import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  OnInit,
  inject,
  signal,
} from '@angular/core';
import { FormBuilder, FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { Api } from '../core/api';
import { codigo, mensajeGeneral } from '../core/errores';
import {
  ESTADOS_TRIAJE,
  EstadoTriaje,
  EventoSeguridad,
  SEVERIDADES,
  Severidad,
  TIPOS_EVENTO,
  TipoEvento,
  entradas,
} from '../core/modelos';
import { StreamEventos } from '../core/stream-eventos';
import { Cargando, FalloServidor } from '../ui/estados';
import { CambioPagina, Paginador } from '../ui/paginador';
import { Opcion, Selector } from '../ui/selector';

@Component({
  selector: 'app-eventos',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [DatePipe, ReactiveFormsModule, RouterLink, Cargando, FalloServidor, Paginador, Selector],
  templateUrl: './eventos.html',
  styleUrl: './eventos.css',
})
export class Eventos implements OnInit {
  private readonly api = inject(Api);
  private readonly stream = inject(StreamEventos);
  private readonly router = inject(Router);
  private readonly ruta = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);

  protected readonly TIPOS = TIPOS_EVENTO;
  protected readonly SEV = SEVERIDADES;
  protected readonly TRIAJE = ESTADOS_TRIAJE;

  protected readonly opcionesTipo: Opcion<TipoEvento | ''>[] = [
    { valor: '', etiqueta: 'Todos' },
    ...entradas(TIPOS_EVENTO).map(([valor, etiqueta]) => ({ valor, etiqueta })),
  ];
  protected readonly opcionesSeveridad: Opcion<Severidad | ''>[] = [
    { valor: '', etiqueta: 'Todas' },
    ...entradas(SEVERIDADES).map(([valor, s]) => ({ valor, etiqueta: s.nombre })),
  ];
  protected readonly opcionesEstado: Opcion<EstadoTriaje | ''>[] = [
    { valor: '', etiqueta: 'Todos' },
    ...entradas(ESTADOS_TRIAJE).map(([valor, e]) => ({ valor, etiqueta: e.nombre })),
  ];

  protected readonly filtros = inject(FormBuilder).nonNullable.group({
    tipo: '' as TipoEvento | '',
    severidad: '' as Severidad | '',
    estado: '' as EstadoTriaje | '',
    ip: ['', Validators.maxLength(45)],
  });

  protected readonly filas = signal<EventoSeguridad[]>([]);
  protected readonly total = signal(0);
  protected readonly desplazamiento = signal(0);
  protected readonly limite = signal(25);
  protected readonly cargando = signal(true);
  protected readonly fallo = signal<number | null>(null);
  protected readonly aviso = signal<{ ok: boolean; texto: string } | null>(null);
  /** Eventos llegados por el stream desde la última carga: se avisa, no se insertan solos. */
  protected readonly nuevos = signal(0);
  protected readonly enVivo = signal(false);

  protected readonly ocupado = signal<number | null>(null);
  protected readonly editandoNota = signal<number | null>(null);
  protected readonly textoNota = new FormControl('', {
    nonNullable: true,
    validators: Validators.maxLength(1000),
  });

  /** Filtros con los que se hizo la última carga (para el estado vacío y el botón Limpiar). */
  protected readonly hayFiltros = signal(false);

  ngOnInit(): void {
    // Filtros desde la URL: permite enlazar p. ej. /eventos?ip=203.0.113.7
    const q = this.ruta.snapshot.queryParamMap;
    this.filtros.setValue({
      tipo: (q.get('tipo') as TipoEvento) ?? '',
      severidad: (q.get('severidad') as Severidad) ?? '',
      estado: (q.get('estado') as EstadoTriaje) ?? '',
      ip: q.get('ip') ?? '',
    });
    void this.cargar();

    const cerrar = this.stream.suscribir(
      (e, clase) => {
        if (clase === 'triaje') {
          this.filas.update((lista) => lista.map((x) => (x.id === e.id ? e : x)));
        } else {
          this.nuevos.update((n) => n + 1);
        }
      },
      (conectado) => this.enVivo.set(conectado),
    );
    this.destroyRef.onDestroy(cerrar);
  }

  async cargar(): Promise<void> {
    this.cargando.set(true);
    this.fallo.set(null);
    try {
      const v = this.filtros.getRawValue();
      this.hayFiltros.set(Boolean(v.tipo || v.severidad || v.estado || v.ip.trim()));
      const pagina = await this.api.eventos({
        tipo: v.tipo,
        severidad: v.severidad,
        estado: v.estado,
        origen_ip: v.ip.trim(),
        limite: this.limite(),
        desplazamiento: this.desplazamiento(),
      });
      this.filas.set(pagina.elementos);
      this.total.set(pagina.total);
      this.nuevos.set(0);
    } catch (e) {
      // Una IP mal escrita da 422: se trata como «sin resultados», no como fallo del servidor
      if (codigo(e) === 422) {
        this.filas.set([]);
        this.total.set(0);
      } else {
        this.fallo.set(codigo(e));
      }
    } finally {
      this.cargando.set(false);
    }
  }

  aplicar(): void {
    this.desplazamiento.set(0);
    const v = this.filtros.getRawValue();
    void this.router.navigate([], {
      queryParams: {
        tipo: v.tipo || null,
        severidad: v.severidad || null,
        estado: v.estado || null,
        ip: v.ip.trim() || null,
      },
      replaceUrl: true,
    });
    void this.cargar();
  }

  limpiar(): void {
    this.filtros.reset();
    this.aplicar();
  }

  filtrarIp(ip: string): void {
    this.filtros.controls.ip.setValue(ip);
    this.aplicar();
  }

  verNuevos(): void {
    this.desplazamiento.set(0);
    void this.cargar();
  }

  paginar({ desplazamiento, limite }: CambioPagina): void {
    this.desplazamiento.set(desplazamiento);
    this.limite.set(limite);
    void this.cargar();
  }

  // --- Triaje (mismas acciones que el feed de Monitorización) ---

  private reemplazar(e: EventoSeguridad): void {
    this.filas.update((lista) => lista.map((x) => (x.id === e.id ? e : x)));
  }

  async triar(e: EventoSeguridad, estado: EstadoTriaje): Promise<void> {
    if (e.estado_triaje === estado) return;
    this.ocupado.set(e.id);
    this.aviso.set(null);
    try {
      this.reemplazar(await this.api.triarEvento(e.id, { estado }));
    } catch (err) {
      this.aviso.set({ ok: false, texto: mensajeGeneral(err) });
    } finally {
      this.ocupado.set(null);
    }
  }

  abrirNota(e: EventoSeguridad): void {
    this.textoNota.setValue(e.nota ?? '');
    this.editandoNota.set(e.id);
  }

  async guardarNota(e: EventoSeguridad): Promise<void> {
    if (this.textoNota.invalid) return;
    this.ocupado.set(e.id);
    try {
      this.reemplazar(await this.api.triarEvento(e.id, { nota: this.textoNota.value.trim() }));
      this.editandoNota.set(null);
    } catch (err) {
      this.aviso.set({ ok: false, texto: mensajeGeneral(err) });
    } finally {
      this.ocupado.set(null);
    }
  }

  async abrirIncidencia(e: EventoSeguridad): Promise<void> {
    this.ocupado.set(e.id);
    this.aviso.set(null);
    try {
      const incidente = await this.api.incidenteDesdeEvento(e.id);
      await this.router.navigate(['/incidentes', incidente.id]);
    } catch (err) {
      this.aviso.set({ ok: false, texto: mensajeGeneral(err) });
    } finally {
      this.ocupado.set(null);
    }
  }
}
