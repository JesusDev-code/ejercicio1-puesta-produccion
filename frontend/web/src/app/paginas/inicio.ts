import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Glifos } from '../ui/glifos';
import { Marca } from '../ui/marca';

interface Servicio {
  codigo: string;
  titulo: string;
  texto: string;
}

interface Plan {
  nombre: string;
  precio: string;
  periodo: string;
  para: string;
  incluye: string[];
  destacado?: boolean;
}

const SERVICIOS: Servicio[] = [
  {
    codigo: '01',
    titulo: 'Sensores señuelo',
    texto:
      'Desplegamos servicios trampa en tu perímetro. Nadie legítimo los usa, así que cada visita es una señal: sondeos, escáneres y robos de credenciales se ven en cuanto empiezan.',
  },
  {
    codigo: '02',
    titulo: 'Monitorización continua',
    texto:
      'Un panel en tiempo real con cada evento clasificado por tipo y severidad. Nuestros analistas lo revisan, descartan el ruido y escalan lo que importa.',
  },
  {
    codigo: '03',
    titulo: 'Gestión de incidencias',
    texto:
      'Tu equipo reporta cualquier sospecha desde Umbral, nuestra plataforma. Un analista asignado la investiga y la lleva hasta el cierre, con notas y estados visibles.',
  },
  {
    codigo: '04',
    titulo: 'Trazabilidad y cumplimiento',
    texto:
      'Cada acción queda registrada en un log de auditoría. Te ayudamos a documentar los incidentes que debas notificar, como una brecha de datos personales.',
  },
];

const PASOS = [
  { titulo: 'Detectamos', texto: 'Los sensores registran la actividad sospechosa contra tu empresa.' },
  { titulo: 'Analizamos', texto: 'Un analista hace el triaje: ruido, revisado o incidencia.' },
  { titulo: 'Respondemos', texto: 'La incidencia se gestiona contigo hasta cerrarla, paso a paso.' },
];

const PLANES: Plan[] = [
  {
    nombre: 'Esencial',
    precio: '290 €',
    periodo: '/ mes',
    para: 'Pymes que empiezan a vigilar su perímetro',
    incluye: [
      '1 sensor señuelo',
      'Panel de eventos en tiempo real',
      'Hasta 10 usuarios en Umbral',
      'Revisión de eventos en horario laboral',
      'Respuesta en 24 h laborables',
    ],
  },
  {
    nombre: 'Profesional',
    precio: '690 €',
    periodo: '/ mes',
    para: 'Empresas con datos sensibles o atención al público',
    incluye: [
      '3 sensores señuelo',
      'Analista asignado a tu cuenta',
      'Usuarios ilimitados en Umbral',
      'Vigilancia 24/7 de eventos críticos',
      'Respuesta en 4 h',
      'Informe mensual de actividad',
    ],
    destacado: true,
  },
  {
    nombre: 'Empresa',
    precio: 'A medida',
    periodo: '',
    para: 'Varias sedes o requisitos de cumplimiento propios',
    incluye: [
      'Sensores sin límite',
      'Equipo de analistas dedicado',
      'Acuerdo de nivel de servicio (SLA) propio',
      'Apoyo en la notificación de incidentes',
      'Revisión trimestral con dirección',
    ],
  },
];

const CLIENTES = ['Transportes Ibarra', 'Clínica Solana', 'Hotel Mirador'];

@Component({
  selector: 'app-inicio',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, Glifos, Marca],
  styleUrl: './inicio.css',
  template: `
    <div class="pagina inicio">
      <header class="barra">
        <app-marca nombre="Kaelum" subtitulo="SECURITY" [tam]="34" />
        <nav aria-label="Secciones" class="enlaces">
          <a href="#servicios" (click)="ir($event, 'servicios')">Servicios</a>
          <a href="#planes" (click)="ir($event, 'planes')">Planes</a>
          <a href="#contacto" (click)="ir($event, 'contacto')">Contacto</a>
        </nav>
        <a routerLink="/login" class="btn btn-oro">Acceso clientes <span aria-hidden="true">→</span></a>
      </header>

      <main>
        <section class="heroe" aria-labelledby="titulo-heroe">
          <app-glifos [densidad]="45" />
          <div class="heroe-texto">
            <span class="etiqueta-mono">CIBERSEGURIDAD GESTIONADA PARA PYMES</span>
            <h1 id="titulo-heroe" class="lema">
              Vigilamos tu red <span class="cursiva-sangre">mientras tú trabajas.</span>
            </h1>
            <p class="entradilla">
              Kaelum Security es tu equipo de seguridad externo. Detectamos lo que intenta entrar, lo
              analizamos y gestionamos cada incidencia contigo desde Umbral, nuestra plataforma.
            </p>
            <div class="acciones">
              <a href="#planes" class="btn btn-sangre" (click)="ir($event, 'planes')">Ver planes</a>
              <a routerLink="/login" class="btn btn-suave">Ya soy cliente</a>
            </div>
          </div>
        </section>

        <section id="servicios" class="seccion" aria-labelledby="titulo-servicios">
          <span class="etiqueta-mono">QUÉ HACEMOS</span>
          <h2 id="titulo-servicios" class="titulo">Seguridad de principio a fin</h2>
          <div class="rejilla servicios">
            @for (s of servicios; track s.codigo) {
              <article class="cristal tarjeta">
                <span class="num">{{ s.codigo }}</span>
                <h3>{{ s.titulo }}</h3>
                <p>{{ s.texto }}</p>
              </article>
            }
          </div>
        </section>

        <section class="seccion" aria-labelledby="titulo-pasos">
          <span class="etiqueta-mono">CÓMO FUNCIONA</span>
          <h2 id="titulo-pasos" class="titulo">Tres pasos, <span class="cursiva-sangre">ningún cabo suelto</span></h2>
          <ol class="pasos">
            @for (p of pasos; track p.titulo; let i = $index) {
              <li>
                <span class="paso-num">{{ i + 1 }}</span>
                <div>
                  <h3>{{ p.titulo }}</h3>
                  <p>{{ p.texto }}</p>
                </div>
              </li>
            }
          </ol>
        </section>

        <section id="planes" class="seccion" aria-labelledby="titulo-planes">
          <span class="etiqueta-mono">PLANES</span>
          <h2 id="titulo-planes" class="titulo">Un plan para cada tamaño</h2>
          <p class="subtitulo">Precios mensuales sin permanencia. IVA no incluido.</p>
          <div class="rejilla planes">
            @for (plan of planes; track plan.nombre) {
              <article class="cristal plan" [class.destacado]="plan.destacado">
                @if (plan.destacado) {
                  <span class="sello">EL MÁS ELEGIDO</span>
                }
                <h3>{{ plan.nombre }}</h3>
                <p class="para">{{ plan.para }}</p>
                <p class="precio">
                  {{ plan.precio }}<span class="periodo">{{ plan.periodo }}</span>
                </p>
                <ul>
                  @for (item of plan.incluye; track item) {
                    <li>{{ item }}</li>
                  }
                </ul>
                <a href="#contacto" class="btn btn-bloque" [class.btn-sangre]="plan.destacado" [class.btn-oro]="!plan.destacado" (click)="ir($event, 'contacto')">
                  {{ plan.precio === 'A medida' ? 'Hablemos' : 'Contratar' }}
                </a>
              </article>
            }
          </div>
        </section>

        <section class="seccion clientes" aria-labelledby="titulo-clientes">
          <span id="titulo-clientes" class="etiqueta-mono">CONFÍAN EN NOSOTROS</span>
          <ul class="logos">
            @for (c of clientes; track c) {
              <li>{{ c }}</li>
            }
          </ul>
        </section>

        <section id="contacto" class="seccion contacto cristal" aria-labelledby="titulo-contacto">
          <h2 id="titulo-contacto" class="titulo">¿Hablamos?</h2>
          <p class="subtitulo">
            Cuéntanos cómo es tu empresa y te proponemos un plan. Si ya eres cliente, entra en Umbral
            con la cuenta que te dio tu administrador.
          </p>
          <div class="acciones">
            <a href="mailto:comercial@kaelum.example" class="btn btn-sangre">comercial&#64;kaelum.example</a>
            <a routerLink="/login" class="btn btn-oro">Acceso clientes <span aria-hidden="true">→</span></a>
          </div>
        </section>
      </main>

      <footer class="pie-web">
        <span>© 2026 Kaelum Security</span>
        <span class="aviso-ficticio">
          Empresa ficticia: proyecto académico de Puesta en producción segura. No se presta ningún servicio real.
        </span>
      </footer>
    </div>
  `,
})
export class Inicio {
  protected readonly servicios = SERVICIOS;
  protected readonly pasos = PASOS;
  protected readonly planes = PLANES;
  protected readonly clientes = CLIENTES;

  /** Desplazamiento suave a una sección sin cambiar de ruta. */
  protected ir(evento: Event, id: string): void {
    evento.preventDefault();
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}
