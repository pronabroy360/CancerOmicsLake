args <- commandArgs(trailingOnly=TRUE)
root <- args[1]
directory <- file.path(root,"figures")
dir.create(directory,showWarnings=FALSE)
settings <- list(family="sans",width=9,height=5)

values <- read.csv(file.path(root,"tables/numerical_environments.csv"))
svg(file.path(directory,"numerical_environments.svg"),width=9,height=4)
par(mar=c(4,8,3,2))
control <- values$spearman[values$environment=="macos142"]
delta <- (values$spearman-control)/1e-9
plot(delta,seq_len(nrow(values)),yaxt="n",pch=19,col="#176b75",
     xlab="Spearman difference from macOS control (units of 1e-9)",ylab="",
     xlim=range(delta)+c(-1,1)*2,
     main="Recorded OS difference persists under both Polars versions")
axis(2,at=seq_len(nrow(values)),labels=values$environment,las=1)
text(delta,seq_len(nrow(values)),sprintf("%.12f",values$spearman),pos=3,cex=.7)
dev.off()

effects <- read.csv(file.path(root,"tables/processing_effects.csv"))
top <- read.csv(file.path(root,"tables/processing_topk.csv"))
effects <- effects[effects$universe=="all_shared",]
top <- top[top$universe=="all_shared" & top$top_k==50,]
svg(file.path(directory,"processing_concordance.svg"),width=10,height=4)
par(mfrow=c(1,2),mar=c(5,4,3,1))
barplot(effects$kendall_tau_b,names.arg=sub("TCGA-","",effects$cancer_type),
        col="#176b75",ylim=c(0,1),ylab="Signed-effect Kendall tau-b",main="Broad effect concordance")
barplot(top$tie_mean_jaccard,names.arg=sub("TCGA-","",top$cancer_type),
        col="#c46936",ylim=c(0,.01),ylab="Mean top-50 Jaccard",main="Tie-aware leading-list agreement")
dev.off()

timings <- read.csv(file.path(root,"tables/workflow_timings.csv"))
timings$group <- sub("_(10|20|30)$","",timings$workload)
timings$size <- as.integer(sub("^.*_","",timings$workload))
svg(file.path(directory,"workflow_module_timings.svg"),width=12,height=7)
par(mfrow=c(2,4),mar=c(4,4,3,1),oma=c(3,0,0,0))
for (group in sort(unique(timings$group))) {
  block <- timings[timings$group==group,]
  plot(NA,xlim=c(10,30),ylim=c(0,max(block$median_seconds)*1.1),
       xlab="Specimens",ylab="Median seconds",main=group,cex.main=.8)
  for (tool in c("reference","extension")) {
    b <- block[block$tool==tool,]
    med <- aggregate(median_seconds~size,data=b,FUN=median)
    lines(med$size,med$median_seconds,type="b",pch=19,
          col=if(tool=="reference") "#176b75" else "#c46936")
  }
}
plot.new()
legend("center",legend=c("Published R module","Polars benchmark extension"),
       col=c("#176b75","#c46936"),pch=19,bty="n",cex=.85)
mtext("Shared TMM; AMD64 emulation; batch startup/raw reads excluded; Python child/I/O included",side=1,outer=TRUE,line=1,cex=.7)
dev.off()
