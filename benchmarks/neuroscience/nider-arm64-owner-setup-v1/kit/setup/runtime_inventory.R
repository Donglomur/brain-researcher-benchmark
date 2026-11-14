# Future dependency metadata only. No neuroscience inputs, estimator or fit.
args <- commandArgs(trailingOnly = TRUE)
stopifnot(length(args) == 3L, identical(as.character(getRversion()), "4.3.2"))
.libPaths(c("/opt/nider/library", .Library))
lock <- jsonlite::fromJSON(args[[1]], simplifyVector = FALSE)
stopifnot(identical(lock$schema, "nider_portable_setup_lock_v1"),
          length(lock$R_packages) == 68L, length(lock$OS_packages) == 14L)
sha <- function(path) {
  stopifnot(file.exists(path), !dir.exists(path), !grepl("[\r\n]", path))
  x <- system2("sha256sum", shQuote(path), stdout = TRUE)
  stopifnot(length(x) == 1L, is.null(attr(x,"status")) || attr(x,"status") == 0L,
            grepl("^[a-f0-9]{64} ", x))
  substr(x,1L,64L)
}
tree <- function(root) {
  paths <- sort(list.files(root, recursive = TRUE, all.files = TRUE, full.names = TRUE,
                           include.dirs = TRUE, no.. = TRUE), method = "radix")
  entries <- lapply(paths, function(path) {
    relative <- substring(path, nchar(root)+2L)
    link <- Sys.readlink(path)
    if (!is.na(link) && nzchar(link)) return(list(path=relative,type="symlink",target=link))
    if (dir.exists(path)) return(list(path=relative,type="directory"))
    list(path=relative,type="file",bytes=unname(file.info(path)$size),sha256=sha(path))
  })
  tmp <- tempfile(); on.exit(unlink(tmp))
  writeBin(charToRaw(as.character(jsonlite::toJSON(entries, auto_unbox=TRUE, digits=NA,
                                                null="null", na="null"))),tmp)
  sha(tmp)
}
r_packages <- lapply(lock$R_packages, function(row) {
  actual <- utils::packageDescription(row$Package, lib.loc="/opt/nider/library", fields="Version")
  stopifnot(identical(actual,row$Version))
  list(Package=row$Package,Version=actual)
})
os_packages <- lapply(lock$OS_packages, function(row) {
  query <- paste0(row$Package, if (identical(row$Architecture,"arm64")) ":arm64" else "")
  x <- system2("dpkg-query", c("-W", shQuote("-f=${Version}\t${Architecture}"), shQuote(query)), stdout=TRUE)
  stopifnot(length(x)==1L, is.null(attr(x,"status")) || attr(x,"status")==0L)
  fields <- strsplit(x,"\t",fixed=TRUE)[[1]]
  stopifnot(identical(fields,c(row$Version,row$Architecture)))
  list(Package=row$Package,Version=fields[[1]],Architecture=fields[[2]])
})
config <- function(name) {
  x <- system2(file.path(R.home("bin"),"R"), c("CMD","config",name), stdout=TRUE)
  stopifnot(is.null(attr(x,"status")) || attr(x,"status")==0L)
  paste(x,collapse="\n")
}
blas <- as.character(extSoftVersion()[["BLAS"]])
stopifnot(length(blas)==1L, nzchar(blas), file.exists(blas))
result <- list(schema="nider_portable_dependency_inventory_v1", image=args[[2]],
               R_version=as.character(getRversion()), platform=R.version$platform,
               R_packages=r_packages, OS_packages=os_packages,
               R_home_tree_sha256=tree(R.home()), library_tree_sha256=tree("/opt/nider/library"),
               compiler=list(CC=config("CC"),CXX=config("CXX"),FC=config("FC")),
               BLAS=list(path=blas,sha256=sha(blas)),library_paths=as.list(.libPaths()),
               session=capture.output(utils::sessionInfo()), locale=Sys.getlocale())
stopifnot(identical(.libPaths(),c("/opt/nider/library","/usr/local/lib/R/library")))
writeLines(jsonlite::toJSON(result,auto_unbox=TRUE,digits=NA,null="null",na="null",pretty=TRUE),args[[3]])
