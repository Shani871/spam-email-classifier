from docx import Document
from docx.shared import Inches,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from copy import deepcopy
import re
from pypdf import PdfReader
src=Document('/Users/shanichauhan/Developer/Email Spam/Email_Spam_Detection_Documentation.docx')
d=Document();s=d.sections[0];s.page_width=Inches(8.2677);s.page_height=Inches(11.6929)
s.top_margin=Inches(.85);s.bottom_margin=Inches(.8);s.left_margin=Inches(1);s.right_margin=Inches(.85)
for name in ['Normal','Title','Heading 1','Heading 2','Heading 3','List Bullet']:
 st=d.styles[name];st.font.name='Times New Roman';st.font.color.rgb=RGBColor(0,0,0);st.font.size=Pt(12)
 st.paragraph_format.space_after=Pt(7);st.paragraph_format.line_spacing=1.15
for name,size in [('Title',18),('Heading 1',17),('Heading 2',14),('Heading 3',12)]:
 st=d.styles[name];st.font.size=Pt(size);st.font.bold=True;st.paragraph_format.keep_with_next=True
 st.paragraph_format.space_before=Pt(12)
foot=s.footer.paragraphs[0];foot.alignment=1
fld=OxmlElement('w:fldSimple');fld.set(qn('w:instr'),'PAGE');foot._p.append(fld)
s.different_first_page_header_footer=True

def p(t='',style=None,center=False,bold=False,size=None):
 a=d.add_paragraph(t,style);a.alignment=WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.JUSTIFY
 for r in a.runs:
  r.bold=bold if not style else r.bold
  if size:r.font.size=Pt(size)
 return a
def page(title):
 d.add_page_break();p(title,'Heading 1',True)
def cp(t,b=False,z=12):return p(t,center=True,bold=b,size=z)
cp('An',True,16);cp('Internship Project Report',True,18);cp('On',True,16)
p();cp('Email Spam and Scam Detection System',True,18);cp('Using Machine Learning and Natural Language Processing',True,16)
p();cp('Submitted in partial fulfilment of the requirements');cp('for the award of the degree of');cp('MASTER OF COMPUTER APPLICATIONS',True,15)
cp('Submitted by');cp('[STUDENT NAME]  ([ROLL NUMBER])',True,14);cp('Under the guidance of');cp('[GUIDE NAME]',True,14);cp('[Designation]')
try:
 im=list(PdfReader('/Users/shanichauhan/Downloads/Resume_Phraser_Report_Final_Edited.pdf').pages[0].images)[0]
 open('tmp/report/logo.png','wb').write(im.data)
 a=d.add_paragraph();a.alignment=1;a.add_run().add_picture('tmp/report/logo.png',width=Inches(1.9))
except Exception:pass
cp('DEPARTMENT OF INFORMATION TECHNOLOGY',True);cp('ANURAG UNIVERSITY',True,14);cp('(Approved by AICTE and NBA Accredited)',True,10)
cp('Venkatapur (V), Ghatkesar (M), Medchal District, Hyderabad, Telangana, 500088',z=10)
cp('Academic Year 2026 2027',True);cp('Batch 2025 2027',True);cp('29 October 2026')
page('CERTIFICATE');cp('ANURAG UNIVERSITY',True,16);cp('DEPARTMENT OF INFORMATION TECHNOLOGY',True)
p('This is to certify that the internship project report entitled “Email Spam and Scam Detection System Using Machine Learning and Natural Language Processing” is a bonafide work carried out and submitted by [STUDENT NAME] ([ROLL NUMBER]) in partial fulfilment of the requirements for the award of the degree of Master of Computer Applications at Anurag University during the batch 2025–2027.')
p('The work was carried out under the guidance of [GUIDE NAME].')
p();p();p('Internal Guide                                      Head of the Department',bold=True);p('[GUIDE NAME]                                  [HOD NAME]');p('[Designation]                                    [Designation]')
page('ACKNOWLEDGEMENT')
p('I express my sincere gratitude to my project guide, [GUIDE NAME], Department of Information Technology, Anurag University, for guidance, suggestions and encouragement during this project.')
p('I thank [HOD NAME], Head of the Department, and the MCA programme coordinator for their academic support. I also thank the faculty members who supported my learning and development throughout the programme.')
p('Finally, I thank my family and friends for their encouragement and support during the preparation of this project and report.');p();p('[STUDENT NAME] ([ROLL NUMBER])',bold=True)
page('DECLARATION')
p('I, [STUDENT NAME] ([ROLL NUMBER]), declare that the project report entitled “Email Spam and Scam Detection System Using Machine Learning and Natural Language Processing” is my own work, submitted in partial fulfilment of the requirements for the award of the degree of Master of Computer Applications at Anurag University, Hyderabad.')
p('I declare that sources used in this report have been acknowledged in the references and that this work has not been submitted previously for the award of another degree.');p();p('Place  Hyderabad');p('Date  __________________');p('Signature  __________________');p('[STUDENT NAME] ([ROLL NUMBER])',bold=True)
page('ABSTRACT')
p('The Email Spam and Scam Detection System is a Python application designed to classify email text and explain suspicious patterns. The documented pipeline combines natural language processing, TF-IDF vectorization, engineered features, Naive Bayes, a support vector machine and Random Forest, together with a rule engine for scam categorization. A multi-page Streamlit interface provides email analysis, educational examples and session-based threat analytics.')
p('The documentation describes a curated corpus of 140 legitimate emails across eight categories. It also reports an ensemble accuracy of 96.8%, but does not identify a corresponding labelled spam corpus or reproducible evaluation evidence. These performance figures are therefore retained as reported values rather than validated experimental outcomes. A representative two-class dataset and a leakage-free evaluation are required before detection quality can be established.')
p('The report covers system requirements, background, methodology, architecture, implementation, reported performance, testing and future work. Principal limitations include the small dataset, English-focused processing, uncalibrated confidence scores and the absence of attachment analysis and email authentication checks.')
page('TABLE OF CONTENTS')
contents=['1  INTRODUCTION','2  LITERATURE SURVEY AND PROJECT OBJECTIVES','3  METHODOLOGY','4  IMPLEMENTATION','5  PERFORMANCE EVALUATION','6  TESTING','7  CONCLUSION AND FUTURE SCOPE','REFERENCES','APPENDIX A  DATASET SAMPLE ENTRIES','APPENDIX B  SCAM PATTERN TAXONOMY']
for t in contents:p(t)
page('LIST OF TABLES')
for i,t in enumerate(['Dataset statistics','Email category distribution','Module structure','TF IDF configuration parameters','Risk level mapping','Evaluation metrics','Reported model performance','Reported cross validation results','Dataset sample entries','Scam pattern taxonomy'],1):p(f'{i}    {t}')
page('LIST OF ABBREVIATIONS')
for t in ['AI    Artificial Intelligence','API    Application Programming Interface','CSV    Comma Separated Values','F1    Harmonic mean of precision and recall','FPR    False Positive Rate','HTML    Hypertext Markup Language','ML    Machine Learning','MNB    Multinomial Naive Bayes','NLP    Natural Language Processing','OCR    Optical Character Recognition','RF    Random Forest','ROC AUC    Area Under the Receiver Operating Characteristic Curve','SVM    Support Vector Machine','TF IDF    Term Frequency Inverse Document Frequency','UI    User Interface']:p(t)
# Collect source sections including tables in their original order.
sections={};key=None
for el in src.element.body:
 if el.tag==qn('w:sectPr'):continue
 text=''.join(el.itertext()) if False else ''.join(x.text or '' for x in el.xpath('.//w:t'))
 if el.tag==qn('w:p'):
  st=el.find('w:pPr/w:pStyle',el.nsmap)
  sty=st.get(qn('w:val')) if st is not None else ''
  if sty=='Heading1':
   m=re.match(r'(\d+)\. ',text)
   if m:key=int(m.group(1));sections[key]=[];continue
   if text.startswith('Appendix A'):key=17;sections[key]=[];continue
   if text.startswith('Appendix B'):key=18;sections[key]=[];continue
 if key:sections[key].append(deepcopy(el))
chapters=[('1  INTRODUCTION',[1,2,3]),('2  LITERATURE SURVEY AND PROJECT OBJECTIVES',[4]),('3  METHODOLOGY',[5,6,7,8,9]),('4  IMPLEMENTATION',[10]),('5  PERFORMANCE EVALUATION',[12,13]),('6  TESTING',[11]),('7  CONCLUSION AND FUTURE SCOPE',[15,14]),('REFERENCES',[16]),('APPENDIX A  DATASET SAMPLE ENTRIES',[17]),('APPENDIX B  SCAM PATTERN TAXONOMY',[18])]
labels={1:'Overview of the Domain',2:'Problem Statement',3:'Project Objectives',4:'Background and Related Technologies',5:'Dataset Description and Analysis',6:'System Architecture',7:'Development Methodology',8:'Feature Engineering',9:'Machine Learning Models',10:'Application Design and Modules',11:'Testing and Evaluation',12:'Reported Results',13:'Challenges and Limitations',14:'Future Scope',15:'Conclusion'}
for ci,(title,keys) in enumerate(chapters,1):
 page(title)
 if ci==5:p('Evaluation status  The figures in this chapter are reproduced from the source documentation and remain unverified. The documented dataset contains 140 ham emails and no labelled spam entries. The stated 80/20 split, cross validation results and comparative improvements cannot establish binary detection performance without a documented two-class corpus and reproducible experiment records.',bold=True)
 for j,k in enumerate(keys,1):
  if k<=15:p(f'{ci}.{j}  {labels[k]}','Heading 2')
  for el in sections.get(k,[]):
   if el.tag==qn('w:p'):
    tx=''.join(x.text or '' for x in el.xpath('.//w:t'))
    if not tx.strip() or tx.startswith('Table '):continue
    # Rebuild paragraphs to remove decorative formatting and obsolete numbering.
    st=el.find('w:pPr/w:pStyle',el.nsmap);sty=st.get(qn('w:val')) if st is not None else ''
    if sty in ['Heading2','Heading3']:
     tx=re.sub(r'^\d+(?:\.\d+)*\s*','',tx);p(tx,'Heading 3');continue
    tx=tx.replace('→',' to ').replace('───────────────────────────────────────────────────────','')
    if k==1 and tx.startswith('Electronic mail'):tx='Email is a widely used communication channel and a common delivery mechanism for unsolicited messages, phishing and social engineering. An accessible detection tool can help users examine suspicious text and understand the signals behind a warning.'
    if k==15 and tx.startswith('The Email Spam & Scam Detection System successfully'):tx='The project describes an accessible approach to email spam and scam analysis that combines classical machine learning, text features and explicit scam rules. Its reported 96.8% accuracy requires validation because the documented corpus contains only legitimate messages. The current documentation establishes the design and intended workflow; representative two-class evaluation remains necessary.'
    if k==12 and ('outperforms' in tx or 'contribute' in tx or 'catches ~15%' in tx):tx='Reported finding pending validation: '+tx
    if k==9:tx=re.sub(r'achieves (94\.1|96\.3|95\.8|96\.8)% accuracy',r'is reported to achieve \1% accuracy (unverified)',tx)
    if k==13:tx=tx.replace("During evaluation, class_weight='balanced' is used to mitigate the effects of imbalance, but having a 1:1 ham:spam ratio would produce more reliable precision/recall estimates.","Class weighting cannot substitute for missing spam examples; supervised binary training and evaluation require examples of both classes.")
    a=p(tx,'List Bullet' if sty=='ListBullet' else None)
   else:
    d.element.body.insert(len(d.element.body)-1,el)
# normalize all table typography and borders
for t in d.tables:
 t.autofit=True
 for ri,row in enumerate(t.rows):
  for cell in row.cells:
   pr=cell._tc.get_or_add_tcPr();b=OxmlElement('w:tcBorders')
   for edge in ['top','left','bottom','right']:
    x=OxmlElement('w:'+edge);x.set(qn('w:val'),'single');x.set(qn('w:sz'),'4');x.set(qn('w:color'),'D9D9D9');b.append(x)
   pr.append(b)
   if ri==0:
    sh=OxmlElement('w:shd');sh.set(qn('w:fill'),'EDEDED');pr.append(sh)
   for a in cell.paragraphs:
    a.paragraph_format.space_after=Pt(5);a.paragraph_format.line_spacing=1
    for r in a.runs:r.font.name='Times New Roman';r.font.size=Pt(10);r.font.color.rgb=RGBColor(0,0,0);r.bold=ri==0
  if ri==0:
   rep=OxmlElement('w:tblHeader');row._tr.get_or_add_trPr().append(rep)
# strip inherited hard page breaks and section decorations from copied tables
out='output/report/Email_Spam_Detection_Academic_Report.docx';d.save(out);print(out)
