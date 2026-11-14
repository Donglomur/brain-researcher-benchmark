# Trusted original-kernel worker with durable per-fit host acknowledgments.
args <- commandArgs(trailingOnly=TRUE)
stopifnot(length(args)==3L)
suppressPackageStartupMessages(library(lme4))
suppressPackageStartupMessages(library(jsonlite))
source(args[[1]],local=TRUE)
run <- function() {
  input <- file("stdin","r");on.exit(close(input),add=TRUE)
  sequence <- 0L
  emit <- function(event,payload) {
    sequence <<- sequence+1L
    cat(toJSON(list(event=event,sequence=sequence,payload=payload),auto_unbox=TRUE,
               null='null',na='null',digits=NA),"\n",sep="")
    flush(stdout())
    line <- readLines(input,n=1L,warn=FALSE)
    stopifnot(length(line)==1L)
    ack <- fromJSON(line,simplifyVector=FALSE)
    stopifnot(identical(sort(names(ack)),sort(c('ack','durable_record_sha256'))),
              identical(as.integer(ack$ack),sequence),nchar(ack$durable_record_sha256)==64L)
    invisible(TRUE)
  }
  request <- fromJSON(args[[2]],simplifyVector=FALSE)
  stopifnot(identical(sort(names(request)),sort(c('schema','participant','training','query','clusters'))),
            identical(request$schema,'neural006-case-v1'))
  to_frame <- function(rows) {
    stopifnot(length(rows)>0L);keys <- names(rows[[1]])
    stopifnot(all(vapply(rows,function(x)identical(names(x),keys),logical(1))))
    as.data.frame(setNames(lapply(keys,function(k)unlist(lapply(rows,`[[`,k),use.names=FALSE)),keys),
                  stringsAsFactors=FALSE,check.names=FALSE)
  }
  training <- to_frame(request$training);query <- to_frame(request$query)
  training$sub <- factor(training$participant);query$sub <- factor(rep(request$participant,nrow(query)))
  stopifnot(!request$participant %in% training$original_participant,
    all(is.finite(as.matrix(training[c(all_predictors,targets)]))),
    all(is.finite(as.matrix(query[all_predictors]))))
  expected_groups <- length(request$clusters)
  stopifnot(length(unique(training$participant))==expected_groups)
  scaling <- list()
  for (feature in all_predictors) {
    center <- mean(training[[feature]]);spread <- sd(training[[feature]])
    stopifnot(is.finite(center),is.finite(spread));constant <- spread==0
    if (constant) spread <- 1
    training[[feature]] <- (training[[feature]]-center)/spread
    query[[feature]] <- (query[[feature]]-center)/spread
    scaling[[feature]] <- list(center=center,scale=spread,constant=constant)
  }
  emit('context',list(participant=request$participant,training_rows=nrow(training),
    training_groups=expected_groups,source_rows=as.list(as.integer(query$source_row)),scaling=scaling))
  counter <- new.env(parent=emptyenv());counter$calls <- 0L
  counter$on_call <- function(calls)emit('fit_call',list(calls=calls))
  results <- coefficients <- audits <- list();complete <- TRUE
  for (target in targets) {
    normalizer <- training_normalizer(training[[target]],training$participant)
    emit('normalizer',list(target=target,normalizer=normalizer))
    entry <- list(mean=list(status='fit_completed',
      prediction=as.list(rep(normalizer$training_equal_person_mean,nrow(query)))))
    target_audits <- list()
    for (arm in names(arms)) {
      emit('fit_start',list(target=target,arm=arm))
      # Original independent audit's manual cbind and base-R QR/tolerance; no replacement rank method.
      selected <- arms[[arm]]
      x_independent <- do.call(cbind,c(list(rep(1,nrow(training))),lapply(selected,function(k)training[[k]])))
      rank_independent <- qr(x_independent,tol=1e-10)$rank
      target_audits[[arm]] <- list(rank=rank_independent,columns=ncol(x_independent),
        terms=as.list(c('(Intercept)',selected)),method='manual_cbind_base_R_qr',tolerance=1e-10)
      fit <- fit_one(training,query,target,selected,expected_groups,counter)
      emit('fit_result',list(target=target,arm=arm,diagnostic=fit$diagnostic,
        prediction=if(is.null(fit$prediction))NULL else as.list(fit$prediction),
        independent_design=target_audits[[arm]]))
      entry[[arm]] <- list(status=fit$diagnostic$status,
        prediction=if(is.null(fit$prediction))NULL else as.list(fit$prediction),diagnostic=fit$diagnostic)
      if (!identical(fit$diagnostic$status,'fit_completed')) complete <- FALSE
      if (identical(arm,'J') && identical(fit$diagnostic$status,'fit_completed')) {
        d <- fit$diagnostic;b <- unlist(d$coefficients);C <- d$covariance
        i <- match('abs_V',d$covariance_terms);j <- match('abs_R',d$covariance_terms)
        stopifnot(!is.na(i),!is.na(j))
        variance <- C[i,i]+C[j,j]-2*C[i,j];stopifnot(is.finite(variance),variance>=0)
        coefficients[[target]] <- list(estimand='predictive_J_ML_random_intercept_absV_minus_absR',
          contrast=b[['abs_V']]-b[['abs_R']],variance=variance,standard_error=sqrt(variance),
          units='exported_target_amplitude_per_training_sample_SD_of_predictor',
          original_paper_random_slope_REML=FALSE,calibrated_interval=NULL,significance=NULL)
      }
    }
    results[[target]] <- list(normalizer=normalizer,arms=entry);audits[[target]] <- target_audits
  }
  emit('final',list(schema='neural006-reference-v1',participant=request$participant,
    source_rows=as.list(as.integer(query$source_row)),status=if(complete)'complete'else'incomplete',
    results=results,scaling=scaling,predictive_coefficient_contrasts=coefficients,
    independent_design_audits=audits,actual_fit_calls=counter$calls,original_paper_reproduction=FALSE))
}
run()
