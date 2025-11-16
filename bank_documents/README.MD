FOR RUNNING THE QUESTIONS SIMPLY MOVE TO THE INDIVUDLA FOLDER AND RUN EACH PYTHON FILE SPEARATLY

QUESTION - 1(P1)
    . For simplicity server will listen for 1 client only and for  single time the message will be exchanged same for the client

    . If you want to send idfferent messagge you can chnage it in the client code line 8

    . 

QUESTION - 2(P2)
    . As simple Socket library can only listne to one client at a time that's why i have used Multi threading for listening to all the client at the same time

    . Server is simply listen to every connection and threadin allows to create  different process 
    . Client has two function simultaneously running through threading for receiving and sending messsages

QUESTION - 3(P3)
    .MultiThreading is used in this question also
    . To like chat with another client you have to type "CHAT {CLIENT NUMBER}" . For simplicity client number you have to remeber whule running the client.py file . like if run a file first it will be assigned number 1 and so on simultaneoulsy
    . For exiting the chat on either side just type EXIT 
    . Make sure to run all the client process if you want to have multiple chat going on
    . Server shows when client has connected and disconnected
    . One client can talk with one client at one moment
