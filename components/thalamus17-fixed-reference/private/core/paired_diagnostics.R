# Trusted paired diagnostics over admitted candidate/reference scalar endpoints.
# Source-only adapter: no model fits, neural arrays or published-p selection.
args <- commandArgs(trailingOnly=TRUE)
stopifnot(length(args)==3L, as.character(getRversion())=='4.3.1')
stopifnot(as.character(utils::packageVersion('jsonlite'))=='1.8.4',
          as.character(utils::packageVersion('digest'))=='0.6.31')
input <- args[[1L]]; expected_sha <- args[[2L]]; output <- args[[3L]]
stopifnot(grepl('^[0-9a-f]{64}$',expected_sha),file.exists(input),
          !isTRUE(file.info(input)$isdir),file.info(input)$size>0,
          file.info(input)$size<=1000000,!file.exists(output),
          !file.exists(paste0(output,'.next')),dir.exists(dirname(output)))
# Decode the exact captured bytes whose digest was checked, without reopening input.
input_size <- file.info(input)$size
con <- file(input,open='rb')
body <- tryCatch(readBin(con,what='raw',n=as.integer(input_size)+1L),finally=close(con))
stopifnot(length(body)==input_size,
          identical(digest::digest(body,algo='sha256',serialize=FALSE),expected_sha))
x <- jsonlite::fromJSON(rawToChar(body),simplifyVector=FALSE)
exact_names <- function(value,expected) {
  is.list(value) && length(value)==length(expected) &&
    !is.null(names(value)) && !anyDuplicated(names(value)) &&
    identical(sort(names(value)),sort(expected))
}
conditions <- c('Laser_OFF','Laser_ON')
endpoints <- c('source_auto_auc','fixed_auc','accuracy')
stopifnot(exact_names(x,c('schema','session_order','candidate','reference')),
          identical(x$schema,'thalamus_candidate_and_reference_diagnostics_v1'),
          is.list(x$session_order),is.null(names(x$session_order)),
          length(x$session_order)==17L)
identifier <- function(value) {
  is.character(value) && length(value)==1L && !is.na(value) && nzchar(value)
}
stopifnot(all(vapply(x$session_order,identifier,logical(1))))
ids <- vapply(x$session_order,identity,character(1))
stopifnot(!anyDuplicated(ids))
for(arm in c('candidate','reference')) {
  rows <- x[[arm]]
  stopifnot(is.list(rows),is.null(names(rows)),length(rows)==17L)
  for(i in seq_len(17L)) {
    row <- rows[[i]]
    stopifnot(exact_names(row,c('experiment_id','metrics')),
              identifier(row$experiment_id),identical(row$experiment_id,ids[[i]]),
              exact_names(row$metrics,conditions))
    for(condition in conditions) {
      metrics <- row$metrics[[condition]]
      stopifnot(exact_names(metrics,endpoints))
      for(endpoint in endpoints) {
        value <- metrics[[endpoint]]
        stopifnot(is.numeric(value),length(value)==1L,is.finite(value),value>=0,value<=1)
      }
    }
  }
}

summarize_arm <- function(rows) {
  get_values <- function(endpoint,condition) vapply(rows,function(z) {
    v <- z$metrics[[condition]][[endpoint]]
    stopifnot(is.numeric(v),length(v)==1L,is.finite(v),v>=0,v<=1)
    v
  },numeric(1))
describe <- function(endpoint) {
  off<-get_values(endpoint,'Laser_OFF');on<-get_values(endpoint,'Laser_ON');d<-on-off
  nz<-d[d!=0];counts<-tabulate(match(abs(nz),unique(abs(nz))))
  list(endpoint=endpoint,OFF=unname(off),ON=unname(on),ON_minus_OFF=unname(d),
       OFF_mean=mean(off),ON_mean=mean(on),OFF_median=median(off),ON_median=median(on),
       paired_mean=mean(d),paired_median=median(d),n_pairs=length(d),
       positive=sum(d>0),negative=sum(d<0),zero=sum(d==0),nonzero=length(nz),
       tied_absolute_groups=sum(counts>1L),
       observations_in_tied_absolute_groups=sum(counts[counts>1L]),
       exact_eligible=length(nz)==length(d) && !anyDuplicated(abs(nz)))
}
run_test <- function(endpoint,exact,correct,only_if_exact_eligible=FALSE) {
  desc<-describe(endpoint);warnings<-character()
  options<-list(paired=TRUE,alternative='two.sided',mu=0,exact=exact,correct=correct,
                conf.int=FALSE,difference='Laser_ON minus Laser_OFF')
  if(only_if_exact_eligible && !isTRUE(desc$exact_eligible))
    return(list(status='not_eligible',options=options,reason='Zero or tied absolute differences',p_value=NULL))
  if(desc$nonzero==0L)
    return(list(status='undefined_not_computed',options=options,reason='All paired differences are zero',p_value=NULL))
  answer<-tryCatch(withCallingHandlers(stats::wilcox.test(
    unlist(desc$ON),unlist(desc$OFF),paired=TRUE,alternative='two.sided',mu=0,
    exact=exact,correct=correct,conf.int=FALSE),warning=function(w) {
      warnings<<-c(warnings,conditionMessage(w))
      invokeRestart('muffleWarning')
    }),error=function(e)e)
  if(inherits(answer,'error'))return(list(status='error',options=options,
    error=conditionMessage(answer),warnings=as.list(warnings),p_value=NULL))
  list(status=if(is.finite(answer$p.value))'computed_nominal_session_statistic' else 'undefined_nonfinite',
       options=options,method=answer$method,statistic=as.list(answer$statistic),
       p_value=if(is.finite(answer$p.value))answer$p.value else NULL,warnings=as.list(warnings))
}
  list(session_order=as.list(ids),
    descriptive=lapply(endpoints,describe),
    primary=run_test('source_auto_auc',NULL,TRUE),
    sensitivities=list(
      source_auto_asymptotic_continuity=run_test('source_auto_auc',FALSE,TRUE),
      source_auto_asymptotic_no_continuity=run_test('source_auto_auc',FALSE,FALSE),
      source_auto_exact_if_eligible=run_test('source_auto_auc',TRUE,FALSE,TRUE),
      fixed_Randomised_positive_default=run_test('fixed_auc',NULL,TRUE)),
    accuracy_hypothesis_test_performed=FALSE)
}
result <- list(schema='thalamus_candidate_and_reference_paired_diagnostics_v1',
  status='thalamus_paired_diagnostics_completed',input_sha256=expected_sha,
  input_bytes=length(body),session_order=as.list(ids),n_pairs_per_arm=17L,
  conditions=as.list(conditions),endpoints=as.list(endpoints),
  R=R.version.string,stats_version=as.character(utils::packageVersion('stats')),
  jsonlite_version=as.character(utils::packageVersion('jsonlite')),
  digest_version=as.character(utils::packageVersion('digest')),
  candidate=summarize_arm(x$candidate),reference=summarize_arm(x$reference),
  accuracy_units='fraction; ON-minus-OFF is a fraction, not percentage points',
  diagnostic_contrast='Laser_ON minus Laser_OFF',
  native_model_fits=0L,published_p_target=FALSE,full_paper_complete=FALSE,
  limitations=as.list(c(
    'Nominal session-level statistics; correlated sessions and unverified animal mapping prevent calibrated animal inference.',
    'Automatic source ROC orientation uses evaluated labels; fixed orientation remains separately reported.',
    'The three endpoints are supplied by the admitted-prediction scorer, not by candidate metric claims.',
    'These are declared reconstruction settings, not recovered historical author settings; all sensitivities are retained without selection.',
    'No protected improvement, published-p parity or whole-paper qualification.')))
bytes <- charToRaw(enc2utf8(paste0(jsonlite::toJSON(result,auto_unbox=TRUE,digits=17,
  null='null',na='null'),'\n')))
stopifnot(length(bytes)<=1000000,!file.exists(output),!file.exists(paste0(output,'.next')))
# Preserve a partial .next file on a write failure; publish only a completed body.
temporary <- paste0(output,'.next')
con <- file(temporary,open='wb')
tryCatch({writeBin(bytes,con);flush(con)},finally=close(con))
stopifnot(identical(digest::digest(file=temporary,algo='sha256',serialize=FALSE),
                    digest::digest(bytes,algo='sha256',serialize=FALSE)),
          !file.exists(output),file.rename(temporary,output))
terminal <- jsonlite::toJSON(list(status=result$status,bytes=length(bytes),
  sha256=digest::digest(bytes,algo='sha256',serialize=FALSE)),auto_unbox=TRUE)
stopifnot(nchar(terminal,type='bytes')<=4096L)
cat(terminal,'\n')
