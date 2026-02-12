// ========== WEB WORKER PARA PROCESAMIENTO DE DATOS MASIVOS ==========
// Este worker procesa los cálculos pesados sin bloquear la UI principal

let solicitudPorId = {};
let solicitudes = [];

// Recibir mensaje del main thread
self.onmessage = function(event) {
  const { tipo, datos, filtros } = event.data;
  
  try {
    // Almacenar referencias
    solicitudPorId = datos.solicitudPorId;
    solicitudes = datos.solicitudes;
    
    let resultado;
    
    if (tipo === 'generarTablaTop10') {
      resultado = procesarTablaTop10(filtros.idsParaProcesar, filtros.filtroTipo, filtros.filtroEstado, filtros.filtroMes);
    } else if (tipo === 'generarTablaResumen') {
      resultado = procesarTablaResumen(filtros.idsParaProcesar);
    } else if (tipo === 'generarTablaSecciones') {
      resultado = procesarTablaSecciones(filtros.idsParaProcesar);
    }
    
    // Enviar resultado al main thread
    self.postMessage({
      success: true,
      tipo: tipo,
      resultado: resultado
    });
  } catch (error) {
    self.postMessage({
      success: false,
      error: error.message,
      stack: error.stack
    });
  }
};

// ========== PROCESAR TABLA TOP 10 ==========
function procesarTablaTop10(idsParaProcesar, filtroTipo, filtroEstado, filtroMes) {
  let resumenPorTipo = {};
  let totalesPorTipo = {};
  let contadorEstados = { Pendiente: 0, "En atención": 0, otros: 0 };
  
  idsParaProcesar.forEach(id => {
    const s = solicitudPorId[id];
    if (!s) return;
    
    const tipo = s["Tipo de reporte"];
    const estado = s["Estado Reporte"];
    
    if (!tipo || !estado) return;
    
    const estadoTrim = estado.trim();
    if (estadoTrim === "Pendiente") {
      contadorEstados.Pendiente++;
    } else if (estadoTrim === "En atención") {
      contadorEstados["En atención"]++;
    } else {
      contadorEstados.otros++;
    }
    
    let mesClave;
    if (s["Fecha reporte"]) {
      const fecha = new Date(s["Fecha reporte"]);
      if (!isNaN(fecha)) {
        mesClave = fecha.getFullYear()+"-"+(fecha.getMonth()+1).toString().padStart(2,"0");
      } else {
        mesClave = "Sin fecha";
      }
    } else {
      mesClave = "Sin fecha";
    }
    
    if (!resumenPorTipo[tipo]) {
      resumenPorTipo[tipo] = {};
    }
    if (!resumenPorTipo[tipo][mesClave]) {
      resumenPorTipo[tipo][mesClave] = {
        Pendiente: 0,
        "En atención": 0,
        total: 0
      };
    }
    
    if (estadoTrim === "Pendiente") {
      resumenPorTipo[tipo][mesClave].Pendiente++;
      if (!totalesPorTipo[tipo]) {
        totalesPorTipo[tipo] = 0;
      }
      totalesPorTipo[tipo]++;
    } else if (estadoTrim === "En atención") {
      resumenPorTipo[tipo][mesClave]["En atención"]++;
    }
  });
  
  // Obtener TODOS los meses
  let todosLosMeses = new Set();
  for(let tipo in resumenPorTipo) {
    for(let mesClave in resumenPorTipo[tipo]) {
      todosLosMeses.add(mesClave);
    }
  }
  
  let mesesOrdenados = Array.from(todosLosMeses).sort();
  
  // Crear array de objetos con nombre
  const mesesEspecificos = mesesOrdenados.map(mesClave => {
    const [anio, mesNum] = mesClave.split("-");
    const fecha = new Date(anio, parseInt(mesNum)-1);
    let nombreMes = fecha.toLocaleString('es-ES',{month:'long'});
    nombreMes = nombreMes.charAt(0).toUpperCase() + nombreMes.slice(1);
    return { clave: mesClave, nombre: nombreMes };
  });
  
  // Obtener top 10 tipos
  let tiposConTotal = [];
  for(let tipo in totalesPorTipo) {
    tiposConTotal.push({ tipo: tipo, total: totalesPorTipo[tipo] });
  }
  tiposConTotal.sort((a, b) => b.total - a.total);
  let top10 = tiposConTotal.slice(0, 10);
  
  return {
    resumenPorTipo,
    mesesEspecificos,
    top10
  };
}

// ========== PROCESAR TABLA RESUMEN ==========
function procesarTablaResumen(idsParaProcesar) {
  let resumen = {};
  
  idsParaProcesar.forEach(id => {
    const s = solicitudPorId[id];
    if(!s || !s["Fecha reporte"] || !s["Estado Reporte"]) return;
    
    let fecha = new Date(s["Fecha reporte"]);
    if(isNaN(fecha)) return;
    
    let mesClave = fecha.getFullYear()+"-"+(fecha.getMonth()+1).toString().padStart(2,"0");
    if(!resumen[mesClave]) {
      resumen[mesClave] = {
        Atendido:0,
        Pendiente:0,
        "En atención":0,
        "No compete":0,
        PendientesMes:0,
        PendientesAcumulado:0,
        IndicadorDias:0
      };
    }
    
    let estado = s["Estado Reporte"].trim();
    if(estado==="Pendiente"){
      resumen[mesClave].Pendiente++;
    } else if(estado==="En atención"){
      resumen[mesClave]["En atención"]++;
    } else if(estado==="Atendido"){
      resumen[mesClave].Atendido++;
    } else if(estado==="No compete"){
      resumen[mesClave]["No compete"]++;
    }
  });
  
  let mesesOrdenados = Object.keys(resumen).sort();
  
  // Calcular Pendientes/En Atención, acumulado e indicador
  let acumulado = 0;
  let totalMeses = mesesOrdenados.length;
  mesesOrdenados.forEach((m, idx) => {
    const fila = resumen[m];
    fila.PendientesMes = fila.Pendiente + fila["En atención"];
    acumulado += fila.PendientesMes;
    fila.PendientesAcumulado = acumulado;
    
    let distanciaDesdeFinal = (totalMeses - 1) - idx;
    let factor = distanciaDesdeFinal * 30;
    if (distanciaDesdeFinal === 0) factor = 1;
    fila.IndicadorDias = fila.PendientesMes * factor;
  });
  
  return {
    resumen,
    mesesOrdenados
  };
}

// ========== PROCESAR TABLA SECCIONES ==========
function procesarTablaSecciones(idsParaProcesar) {
  let resumen = {};
  let mesesSet = new Set();
  
  idsParaProcesar.forEach(id => {
    const s = solicitudPorId[id];
    if(!s || !s["Fecha reporte"] || !s["Estado Reporte"]) return;
    
    let fecha = new Date(s["Fecha reporte"]);
    if(isNaN(fecha)) return;
    
    const transi = s["transi"] || s["Transi"] || s["TRANSI"] || "Sin sección";
    const mesClave = fecha.getFullYear()+"-"+(fecha.getMonth()+1).toString().padStart(2,"0");
    const estado = s["Estado Reporte"].trim();
    
    mesesSet.add(mesClave);
    
    if(!resumen[transi]) {
      resumen[transi] = {};
    }
    if(!resumen[transi][mesClave]) {
      resumen[transi][mesClave] = { Atendido: 0, Pendiente: 0, "En atención": 0, "No compete": 0 };
    }
    
    if(estado==="Pendiente"){
      resumen[transi][mesClave].Pendiente++;
    } else if(estado==="En atención"){
      resumen[transi][mesClave]["En atención"]++;
    } else if(estado==="Atendido"){
      resumen[transi][mesClave].Atendido++;
    } else if(estado==="No compete"){
      resumen[transi][mesClave]["No compete"]++;
    }
  });
  
  let mesesOrdenados = Array.from(mesesSet).sort();
  
  // Ordenar transiciones
  const ordenEspecifico = ["AA", "BA", "CA", "AB", "BB", "CC", "DD", "Sin sección"];
  let transiciones = Object.keys(resumen).sort((a, b) => {
    const indexA = ordenEspecifico.indexOf(a);
    const indexB = ordenEspecifico.indexOf(b);
    
    if (indexA !== -1 && indexB !== -1) return indexA - indexB;
    if (indexA !== -1) return -1;
    if (indexB !== -1) return 1;
    
    return a.localeCompare(b);
  });
  
  return {
    resumen,
    mesesOrdenados,
    transiciones
  };
}
