from rpy2.robjects.packages import importr
from rpy2 import robjects
import os
from flask import Flask, render_template, request, url_for, flash, redirect, send_file, send_from_directory
from werkzeug.utils import secure_filename
from nltk.corpus import stopwords
import csv
import string
import re 
#print (rpy2.__version__)
foreign=importr("foreign")
en_stops=set(stopwords.words('english'))
#update stopwords
en_stops.remove('not')
newstopwords=['what','why','who','when','where']
en_stops.update(newstopwords)


app=Flask(__name__)

APP_ROOT=os.path.dirname(os.path.abspath(__file__))
@app.route("/")
def index():
  return render_template("upload.html")

@app.route("/upload", methods=['GET','POST'])
def upload():
  target=os.path.join(APP_ROOT,'files/')
  print(target)
  print('request=',request)
  if not os.path.isdir(target):
    os.mkdir(target)
  file=request.files['file']
  
  print('file from request=',file)
  if file.filename=="":
    flash('No selected files')
    return redirect(request.url)
  
  filename=secure_filename(file.filename)
  print(filename)
  destination=os.path.join(target, filename)
  print("saving to ", destination)
  file.save(destination)
  global outfile
  outfile=os.path.splitext(destination)[0]+".csv"
  print ("outfile=",outfile)
  #create dataframe of sav file in r
  robjects.r.assign('dest',destination)
  robjects.r.assign('outfile',outfile)
  robjects.r('dataset1<-read.spss(dest,to.data.frame=TRUE)')
  # resave dataframe as .csv in r
  robjects.r('write.csv(dataset1, file=outfile, row.names=FALSE)')
  # load dataframe in python
  dataset1=robjects.r('dataset1')
  print(robjects.r('names(dataset1)'))
  #extract labels and variables for codebook in r
  robjects.r('lst_seq=seq.int(names(dataset1))')
  robjects.r('lst_names=names(dataset1)')
  robjects.r('lst_variables=attr(dataset1,"variable.labels")')
  #bring codebook lists from r to python
  global a,b,c,t
  a=robjects.r('lst_seq')
  b=robjects.r('lst_names')
  c=robjects.r('lst_variables')
  c_strip=""
  c_stripns=""
  t=0
  # strip stopwords and punctation and create options for labels
  ret=strip_it(c[t])
  print(len(ret))
  c_strip=ret[0]
  c_stripns=ret[1]
  print(a[t],b[t],c[t],c_strip,c_stripns)
  return render_template("edvar.html", name=filename, cur=1, tot=len(c)-1, field=b[t], variable=c[t], stripvariable=c_strip, stripnsv=c_stripns)

@app.route("/next", methods=['GET','POST'])
def next():
  #get new label from form
  print('form=',request.form)
  action=request.form['action']
  if request.form['Answer']!='None':
    newvar=request.form['Answer']
  else:
    newvar=request.form['userAnswer']
    
  print(action,newvar)
  #rewrite c with new userAnswer
  global t
  global codefile
  global outfile
  c[t]=newvar
  print (action, newvar)
  #if next/prev button was selected go forward/backward
  if action=="Next":
    t=t+1
  else:
    t=t-1
  if t<0:
    t=1
  if t>=len(c):
    t=len(c)-1
  head, tail=os.path.split(outfile)
  print('outfile head=',head)
  print('outfile tail=',tail)
  # write button was selected, create output .csv for datafile & codebook
  if action=="Write":
    #write code file to csv
    codefile=head+"/codefile_"+tail
    print('codefile=',codefile)
    rows=zip(a,b,c)
    with open(codefile,"w") as d:
      writer=csv.writer(d)
      for row in rows:
        writer.writerow(row)
    #write data file with new column names
    tmpfile=os.path.splitext(outfile)[0]
    print('split 0=',os.path.splitext(outfile)[0])
    print('split 1=', os.path.splitext(outfile)[1])
    tmpfile=tmpfile+".tmp"
    print('tmpfile=',tmpfile)
    f=open(outfile, 'r')
    data=open(tmpfile, 'w')
    #create new header for datafile
    print(c)
    headerlist=','.join(c)
    print(headerlist)
    #write the new header with modified labels
    data.write(headerlist+"\n")
    #skip first line, and write the rest of the datafile
    lines=f.readlines()[1:]
    data.writelines(lines)
    f.close()
    data.close()
    os.rename(outfile, os.path.splitext(outfile)[0]+".old")
    os.rename(tmpfile,os.path.splitext(outfile)[0]+".csv")
    print('outfile=',outfile)
    # return download web page
    return (render_template("download.html"))
  # if next/prev button selected strip next label/variable
  print (a[t],b[t],c[t],t)
  ret=strip_it(c[t])
  print('words after strip',len(ret), ret)
  c_strip=ret[0]
  c_stripns=ret[1]
  #return edit variable web page for next label/variables
  return render_template("edvar.html", name=tail, cur=t+1, tot=len(c), field=b[t], variable=c[t], stripvariable=c_strip, stripnsv=c_stripns)

@app.route('/return-datafile/')
def return_files_dat():
  #send datafile 
  global outfile
  head, tail = os.path.split(outfile)
  print (outfile, head, tail)
  try:
    return send_from_directory(head, tail, attachment_filename=tail)
  except Exception as e:
    return str(e)
  
@app.route('/return-codefile/')
def return_files_code():
  #send codebook
  global codefile
  head, tail = os.path.split(codefile)
  try:
    return send_from_directory(head, tail, attachment_filename=tail)
  except Exception as e:
    return str(e)

@app.route('/restart')  
def restart(): 
  #restart button selected, clean up previous files and go back to upload.html
  global outfile
  print("outfile=",outfile)
  mydir=os.path.split(outfile)[0]
  print(mydir)
  filelist=[f for f in os.listdir(mydir)]
  for f in filelist:
    print('delete ',f)
    os.remove(os.path.join(mydir,f))
  return render_template('upload.html')

@app.after_request
def add_header(response):
  #purge cache
  response.headers['X-UA-Compatible'] = 'IE=Edge,chrome=1'
  response.headers['Cache-Control'] = 'public, max-age=0'
  return response  
  
def strip_it(initialsent):
  #remove puntuation, stopwords, and add spaces to runon words 
  translator = str.maketrans('', '', string.punctuation)
  newvar=initialsent.translate(translator)
  print('after punctuation strip=',newvar)
  newvar=re.sub(r'([a-z](?=[A-Z])|[A-Z](?=[A-Z][a-z]))', r'\1 ', newvar)
  print('add spaces if necessary=',newvar)
  c_split=newvar.split(" ")
  c_strip=""
  c_stripns=""
  for word in c_split:
    if word not in en_stops:
      c_strip=c_strip+word+" "
      c_stripns=c_stripns+word+"_"
  c_stripns=c_stripns.rstrip('_')
  return (c_stripns,c_strip)
