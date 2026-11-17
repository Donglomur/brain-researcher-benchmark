# Owner-only future execution. Never source the original author script.
# This schedules exact original expressions in declared phases, not whole-file order.
stopifnot(identical(as.character(getRversion()), "4.3.2"))
required <- c(renv="1.0.4", here="1.0.1", readxl="1.4.3", stringr="1.5.1", dplyr="1.1.4",
              meta="7.0.0", metafor="4.6.0", metaBMA="0.6.9", jsonlite="1.8.8", digest="0.6.35")
for (package in names(required)) {
  if (!requireNamespace(package, quietly=TRUE)) stop("Missing installed package: ", package)
  if (packageVersion(package) != package_version(required[[package]])) stop("Package version mismatch: ", package)
}
job <- jsonlite::fromJSON("job.json", simplifyVector=FALSE)
sha_file <- function(path) digest::digest(file=path, algo="sha256", serialize=FALSE)
paths <- c(workbook="data/studyInformation/studyInformation_publication.xlsx",
           script="official.R", lock="original-renv.lock", schema="FIELD_SCHEMA.json")
for (key in names(paths)) stopifnot(identical(sha_file(paths[[key]]), job$pins[[key]]))
for (name in names(job$implementation_hashes))
  stopifnot(identical(sha_file(name), job$implementation_hashes[[name]]))
source("frozen_collector.R", local=TRUE)
source("native_artifacts.R", local=TRUE)
lock <- jsonlite::fromJSON(paths[["lock"]], simplifyVector=FALSE)
schema <- jsonlite::fromJSON(paths[["schema"]], simplifyVector=FALSE)
check_loaded <- function() lapply(loadedNamespaces(), function(package) {
  version <- as.character(packageVersion(package))
  desc <- packageDescription(package)
  if (!identical(desc$Priority, "base")) {
    pinned <- lock$Packages[[package]]
    need(!is.null(pinned) && package_version(pinned$Version) == package_version(version),
         paste("Unpinned or changed loaded dependency", package))
  }
  list(package=package, version=version, path=find.package(package))
})
invisible(check_loaded())
expected_phases <- list(
  libraries=c(13:19,23),
  core_DL=c(28,29,73,74,75,77,86,131,140,141,149,153,216,219,262,265),
  table1=c(31,377,379,380,381), forests=c(165,173,178,229,237,242,274,282,287),
  Bayesian=c(186,187,189,190,192,194,195,197,201,245,247,248,250,255,296,298,299,301,306))
expected_ends <- c(`77`=82,`86`=129,`131`=138,`31`=67,`165`=171,`173`=176,
  `229`=235,`237`=240,`274`=280,`282`=285,`197`=200,`250`=253,`301`=304)
expressions <- parse(paths[["script"]], keep.source=TRUE, encoding="UTF-8")
references <- attr(expressions,"srcref")
lines <- strsplit(readChar(paths[["script"]],file.info(paths[["script"]])$size,useBytes=TRUE),"\n",fixed=TRUE)[[1L]]
need(length(job$expressions)==57L, "exact 57-expression manifest required")
seen <- integer()
for (span in job$expressions) {
  end_line <- if (as.character(span$start) %in% names(expected_ends))
    unname(expected_ends[as.character(span$start)]) else span$start
  need(span$phase %in% names(expected_phases) && span$start %in% expected_phases[[span$phase]] &&
       span$end == end_line && !span$start %in% seen, "unapproved source span")
  seen <- c(seen,span$start)
  text <- paste0(paste(lines[span$start:span$end],collapse="\n"),"\n")
  need(identical(digest::digest(text,algo="sha256",serialize=FALSE),span$sha256), "expression bytes mismatch")
}
need(identical(as.numeric(seen),as.numeric(unlist(expected_phases,use.names=FALSE))),"phase order mismatch")
author_env <- new.env(parent=globalenv())
original <- NULL
warnings_seen <- character()
evaluated <- list()
print_options <- list()
graphics_devices <- list()
output_root <- normalizePath("out",mustWork=TRUE)
get_rng <- function() list(kind=as.list(RNGkind()),
  state=if (exists(".Random.seed",envir=globalenv(),inherits=FALSE))
    as.list(get(".Random.seed",envir=globalenv(),inherits=FALSE)) else NULL,
  source_seed_was_not_overridden=TRUE)
rng_before <- get_rng()
evaluate_span <- function(span) {
  selected <- which(vapply(references,function(ref) ref[1L]==span$start && ref[3L]==span$end,logical(1)))
  need(length(selected)==1L,"whole unique top-level source expression required")
  if (span$start==28L) {
    resolved <- normalizePath(here::here("data","studyInformation","studyInformation_publication.xlsx"),mustWork=TRUE)
    need(identical(resolved,normalizePath(paths[["workbook"]],mustWork=TRUE)) &&
         identical(sha_file(resolved),job$pins$workbook),"authenticated here path before read")
  }
  withCallingHandlers(withVisible(eval(expressions[[selected]],envir=author_env)),warning=function(w) {
    warnings_seen <<- c(warnings_seen,conditionMessage(w))
  })
}
for (phase in names(expected_phases)) {
  for (span in Filter(function(x) identical(x$phase,phase),job$expressions)) {
    visible <- evaluate_span(span)
    evaluated[[length(evaluated)+1L]] <- list(phase=phase,start=span$start,end=span$end,sha256=span$sha256)
    if (span$start %in% c(165L,229L,274L)) {
      graphics_devices[[as.character(span$start)]] <- list(
        bitmap_type=getOption("bitmapType"),device_number=unname(grDevices::dev.cur()),
        device_name=names(grDevices::dev.cur()),capabilities=as.list(capabilities(c("png","cairo","X11"))))
    }
    if (span$start==29L) original <- author_env$dfcorrs
    if (span$start %in% c(190L,248L,299L)) {
      contrast <- c(`190`="quest_self",`248`="amy_quest",`299`="amy_self")[[as.character(span$start)]]
      snapshot_bayes_input(author_env,contrast,full120,output_root)
    }
    if (span$start %in% c(201L,255L,306L)) {
      contrast <- c(`201`="quest_self",`255`="amy_quest",`306`="amy_self")[[as.character(span$start)]]
      need(isTRUE(visible$visible),"original bare-symbol Bayesian print must be visible")
      print_options[[contrast]] <- list(digits=getOption("digits"),width=getOption("width"),
                                        max_print=getOption("max.print"))
      print_path <- file.path(output_root,"bayes",paste0(contrast,".txt"))
      need(!file.exists(print_path),"new Bayesian print path required")
      writeLines(capture.output(print(visible$value)),print_path,useBytes=TRUE)
      snapshot_bayes_model(author_env,contrast,output_root)
    }
  }
  if (phase=="core_DL") {
    full120 <- collect_full120(author_env,original,schema,job$arm,job$pins$workbook)
    jsonlite::write_json(full120,file.path(output_root,"full120.json"),auto_unbox=TRUE,digits=NA)
    snapshot_dl(author_env,full120,output_root)
  }
  if (phase=="table1") snapshot_table(author_env,output_root)
  if (phase=="forests") {
    for (name in c("forestplot_questSelf_nat.png","forestplot_amyQuest_nat.png","forestplot_meta_amySelf_nat.png")) {
      from <- file.path("results","figures",name)
      to <- file.path(output_root,"results","figures",name)
      need(file.exists(from) && file.info(from)$size>0 && !file.exists(to),"original forest output required")
      need(file.copy(from,to,overwrite=FALSE),"forest artifact copy failed")
    }
  }
}
need(length(evaluated)==57L,"complete original expression execution required")
runtime <- list(R_version=as.character(getRversion()),platform=R.version$platform,
  executable_sha256=sha_file(file.path(R.home("bin"),"exec","R")),
  locale=Sys.getlocale(),timezone=Sys.timezone(),loaded_packages=check_loaded(),
  session_info=capture.output(sessionInfo()),warnings=as.list(warnings_seen),
  original_Bayesian_print_options=print_options,original_png_device_observations=graphics_devices,
  evaluated_expression_count=length(evaluated),evaluated_expressions=evaluated,
  phase_schedule="libraries,core_DL,freeze,table1,forests,Bayesian; not whole-script order",
  full120_frozen_before_Bayesian_mutations=TRUE,
  RNG_before=rng_before,RNG_after=get_rng(),
  source_record_count=nrow(original),postmerge_record_count=nrow(author_env$dfcorrs),
  clean_source_replay_not_recovered_historical_ambient_settings=TRUE,
  scientific_agreement_assessed=FALSE)
jsonlite::write_json(runtime,file.path(output_root,"runtime.json"),auto_unbox=TRUE,digits=NA,pretty=TRUE)
